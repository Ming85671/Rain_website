"""Shipment transformations for rainfall correlation analysis."""

import pandas as pd


PORT_ALIASES = {
    "Hinituan & Talavera Islands": "Hinituan&Talavera Islands",
}


def map_shipment_regions(shipments, port_region_map):
    """Return a copy of shipments with canonical port and region columns."""
    out = shipments.copy()
    out["port_key"] = out["load_port"].replace(PORT_ALIASES)
    out["region_group"] = out["port_key"].map(port_region_map)

    unmapped_values = out.loc[out["region_group"].isna(), "load_port"]
    unmapped = sorted(
        {
            "<missing>" if pd.isna(value) else str(value)
            for value in unmapped_values
        }
    )
    if unmapped:
        raise ValueError(f"Unmapped shipment ports: {', '.join(unmapped)}")

    return out


def monday_start(values):
    """Convert date-like values to normalized starts of Monday-based weeks."""
    dates = pd.to_datetime(values, errors="coerce", format="mixed")
    if isinstance(dates, pd.Series):
        return (
            dates - pd.to_timedelta(dates.dt.weekday, unit="D")
        ).dt.normalize()
    return (dates - pd.to_timedelta(dates.weekday, unit="D")).normalize()


def _validated_panel_keys(regions, weeks):
    region_index = pd.Index(regions)
    duplicate_regions = region_index[region_index.duplicated()].unique()
    if len(duplicate_regions):
        labels = sorted(str(region) for region in duplicate_regions)
        raise ValueError(f"Duplicate regions: {', '.join(labels)}")

    parsed_weeks = pd.DatetimeIndex(
        pd.to_datetime(weeks, errors="coerce", format="mixed")
    )
    if parsed_weeks.tz is not None:
        raise ValueError("Supplied weeks must be timezone-naive Mondays")
    if parsed_weeks.isna().any():
        raise ValueError("Supplied weeks must contain valid timezone-naive Mondays")

    normalized_weeks = parsed_weeks.normalize()
    if (normalized_weeks.weekday != 0).any():
        raise ValueError("Supplied weeks must be Mondays")
    if normalized_weeks.duplicated().any():
        raise ValueError("Duplicate weeks are not allowed")

    return region_index, normalized_weeks


def build_shipment_weekly_panel(shipments, regions, weeks):
    """Aggregate shipments onto a complete supplied region-week grid."""
    region_index, week_index = _validated_panel_keys(regions, weeks)
    out = shipments.copy()
    out["load_start_date"] = pd.to_datetime(
        out["load_start_date"], errors="coerce", format="mixed"
    )
    parsed_volume = pd.to_numeric(out["voy_intake_mt"], errors="coerce")
    invalid_volume = parsed_volume.isna()
    if invalid_volume.any():
        row_labels = ", ".join(str(index) for index in out.index[invalid_volume])
        raise ValueError(
            f"Invalid or missing voy_intake_mt at shipment rows: {row_labels}"
        )
    out["voy_intake_mt"] = parsed_volume
    out = out.dropna(subset=["load_start_date", "region_group", "vsl_name"])
    out["week_start"] = monday_start(out["load_start_date"])

    index = pd.MultiIndex.from_product(
        [region_index, week_index], names=["region_group", "week_start"]
    )
    return (
        out.groupby(["region_group", "week_start"])
        .agg(
            shipments=("vsl_name", "size"),
            volume_mt=("voy_intake_mt", "sum"),
        )
        .reindex(index, fill_value=0)
        .reset_index()
    )


def build_rain_weekly_panel(rain, weeks):
    """Aggregate port rainfall into observed regional Monday weeks."""
    _, week_index = _validated_panel_keys([], weeks)
    out = rain.copy()
    out["date"] = pd.to_datetime(
        out["date"], errors="coerce", format="mixed"
    ).dt.normalize()
    parsed_precipitation = pd.to_numeric(
        out["precipitation_mm"], errors="coerce"
    )
    invalid_precipitation = parsed_precipitation.isna() | parsed_precipitation.isin(
        [float("inf"), float("-inf")]
    )
    if invalid_precipitation.any():
        row_labels = ", ".join(
            str(index) for index in out.index[invalid_precipitation]
        )
        raise ValueError(
            "Invalid or missing precipitation_mm at rainfall rows: "
            f"{row_labels}"
        )
    out["precipitation_mm"] = parsed_precipitation
    out = out.dropna(
        subset=["region_group", "port_name", "date", "precipitation_mm"]
    )
    out["week_start"] = monday_start(out["date"])
    out = out[out["week_start"].isin(week_index)]

    port_daily = (
        out.groupby(
            ["region_group", "date", "week_start", "port_name"],
            as_index=False,
        )
        .agg(port_rain_mm=("precipitation_mm", "mean"))
    )
    regional_daily = (
        port_daily.groupby(
            ["region_group", "date", "week_start"], as_index=False
        )
        .agg(
            daily_rain_mm=("port_rain_mm", "mean"),
            port_count=("port_name", "nunique"),
        )
    )
    return (
        regional_daily.groupby(["region_group", "week_start"], as_index=False)
        .agg(
            rain_mm_day=("daily_rain_mm", "mean"),
            rain_days=("date", "nunique"),
            min_ports=("port_count", "min"),
        )
    )


def add_weekly_anomalies(panel):
    """Add region-specific ISO-week anomalies for rain and shipment metrics."""
    out = panel.copy()
    week_start = pd.to_datetime(out["week_start"], format="mixed")
    out["iso_week"] = week_start.dt.isocalendar().week.astype(int)
    for column in ("rain_mm_day", "shipments", "volume_mt"):
        baseline = out.groupby(["region_group", "iso_week"])[column].transform(
            "mean"
        )
        out[f"{column}_anomaly"] = out[column] - baseline
    return out


def correlation(left, right, rank=False):
    """Return pairwise Pearson correlation, optionally after average ranking."""
    pairs = _paired_values(left, right)
    if (
        len(pairs) < 3
        or pairs["left"].nunique() < 2
        or pairs["right"].nunique() < 2
    ):
        return float("nan")
    if rank:
        pairs = pairs.rank(method="average")
    return float(pairs["left"].corr(pairs["right"]))


def _paired_values(left, right):
    return pd.DataFrame(
        {
            "left": pd.Series(left).reset_index(drop=True),
            "right": pd.Series(right).reset_index(drop=True),
        }
    ).dropna()


def _pair_count(left, right):
    return int(_paired_values(left, right).shape[0])


def calculate_lag_correlations(panel, scope_column="region_group", max_lag=4):
    """Calculate correlations where rain leads by exact calendar weeks.

    ``active_weeks`` counts positive observations for each metric across the
    full scope and therefore does not vary by lag.
    """
    rows = []
    for scope, group in panel.groupby(scope_column, sort=False):
        group = group.copy()
        group["week_start"] = pd.to_datetime(group["week_start"], format="mixed")
        group = group.sort_values("week_start")
        for metric in ("shipments", "volume_mt"):
            active_weeks = int((group[metric] > 0).sum())
            metric_by_week = group.set_index("week_start")[metric]
            anomaly_by_week = group.set_index("week_start")[f"{metric}_anomaly"]
            for lag in range(max_lag + 1):
                future_weeks = group["week_start"] + pd.Timedelta(weeks=lag)
                future_metric = metric_by_week.reindex(future_weeks)
                future_anomaly = anomaly_by_week.reindex(future_weeks)
                rows.append(
                    {
                        "scope": scope,
                        "metric": metric,
                        "rain_leads_weeks": lag,
                        "pearson_raw": correlation(
                            group["rain_mm_day"], future_metric
                        ),
                        "spearman_raw": correlation(
                            group["rain_mm_day"], future_metric, rank=True
                        ),
                        "pearson_anomaly": correlation(
                            group["rain_mm_day_anomaly"], future_anomaly
                        ),
                        "weeks": _pair_count(
                            group["rain_mm_day"], future_metric
                        ),
                        "active_weeks": active_weeks,
                    }
                )
    return pd.DataFrame(rows)


def calculate_monthly_correlations(panel):
    """Calculate region-first raw and month-of-year adjusted correlations."""
    monthly_source = panel.copy()
    week_start = pd.to_datetime(monthly_source["week_start"], format="mixed")
    monthly_source["month"] = week_start.dt.to_period("M").dt.to_timestamp()
    monthly = (
        monthly_source.groupby(["region_group", "month"], as_index=False)
        .agg(
            rain_mm_day=("rain_mm_day", "mean"),
            shipments=("shipments", lambda values: values.sum(min_count=1)),
            volume_mt=("volume_mt", lambda values: values.sum(min_count=1)),
        )
    )
    monthly["month_of_year"] = monthly["month"].dt.month
    for column in ("rain_mm_day", "shipments", "volume_mt"):
        baseline = monthly.groupby(["region_group", "month_of_year"])[
            column
        ].transform("mean")
        monthly[f"{column}_anomaly"] = monthly[column] - baseline

    rows = []
    for region, group in monthly.groupby("region_group", sort=False):
        for metric in ("shipments", "volume_mt"):
            rows.append(
                {
                    "scope": region,
                    "metric": metric,
                    "pearson_raw": correlation(
                        group["rain_mm_day"], group[metric]
                    ),
                    "pearson_anomaly": correlation(
                        group["rain_mm_day_anomaly"],
                        group[f"{metric}_anomaly"],
                    ),
                    "spearman_raw": correlation(
                        group["rain_mm_day"], group[metric], rank=True
                    ),
                    "months": _pair_count(
                        group["rain_mm_day"], group[metric]
                    ),
                }
            )
    return pd.DataFrame(rows)
