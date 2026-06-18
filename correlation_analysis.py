"""Offline rainfall and shipment correlation analysis."""

import argparse
from numbers import Integral
from pathlib import Path

import pandas as pd

import rain


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
    invalid_volume = parsed_volume.isna() | parsed_volume.isin(
        [float("inf"), float("-inf")]
    )
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
    negative_precipitation = out["precipitation_mm"] < 0
    if negative_precipitation.any():
        row_labels = ", ".join(
            str(index) for index in out.index[negative_precipitation]
        )
        raise ValueError(
            f"Negative precipitation_mm at rainfall rows: {row_labels}"
        )
    invalid_date = out["date"].isna()
    if invalid_date.any():
        row_labels = ", ".join(str(index) for index in out.index[invalid_date])
        raise ValueError(
            f"Invalid or missing date at rainfall rows: {row_labels}"
        )
    for column in ("region_group", "port_name"):
        missing = out[column].isna()
        if missing.any():
            row_labels = ", ".join(str(index) for index in out.index[missing])
            raise ValueError(
                f"Missing {column} at rainfall rows: {row_labels}"
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
    pairs = pd.DataFrame(
        {
            "left": pd.Series(left).reset_index(drop=True),
            "right": pd.Series(right).reset_index(drop=True),
        }
    ).dropna()
    non_finite = pairs.isin([float("inf"), float("-inf")]).any(axis=1)
    return pairs.loc[~non_finite]


def _pair_count(left, right):
    return int(_paired_values(left, right).shape[0])


def _validated_lag_panel(panel, scope_column):
    out = panel.copy()
    parsed_values = []
    timezone_aware = []
    for value in out["week_start"]:
        try:
            parsed = pd.Timestamp(value)
        except (TypeError, ValueError):
            parsed = pd.NaT
        parsed_values.append(parsed)
        timezone_aware.append(
            not pd.isna(parsed) and parsed.tz is not None
        )

    parsed_weeks = pd.Series(parsed_values, index=out.index)
    invalid = parsed_weeks.isna()
    if invalid.any():
        row_labels = ", ".join(str(index) for index in out.index[invalid])
        raise ValueError(
            f"Invalid or missing week_start at panel rows: {row_labels}"
        )
    if any(timezone_aware):
        raise ValueError("week_start must be timezone-naive")

    parsed_weeks = pd.to_datetime(parsed_weeks).dt.normalize()
    non_monday = parsed_weeks.dt.weekday != 0
    if non_monday.any():
        row_labels = ", ".join(str(index) for index in out.index[non_monday])
        raise ValueError(
            f"week_start must contain Mondays; invalid panel rows: {row_labels}"
        )
    out["week_start"] = parsed_weeks

    duplicate = out.duplicated(
        subset=[scope_column, "week_start"], keep=False
    )
    if duplicate.any():
        row_labels = ", ".join(str(index) for index in out.index[duplicate])
        raise ValueError(
            f"Duplicate week_start values within {scope_column} "
            f"at panel rows: {row_labels}"
        )
    return out


def calculate_lag_correlations(panel, scope_column="region_group", max_lag=4):
    """Calculate correlations where rain leads by exact calendar weeks.

    ``active_weeks`` counts positive observations for each metric across the
    full scope and therefore does not vary by lag.
    """
    if (
        isinstance(max_lag, bool)
        or not isinstance(max_lag, Integral)
        or max_lag < 0
    ):
        raise ValueError("max_lag must be a non-negative integer")

    panel = _validated_lag_panel(panel, scope_column)
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


def build_national_panel(regional_panel):
    """Build weekly national totals and fixed metric-specific rainfall weights."""
    panel = regional_panel.copy()
    panel["week_start"] = pd.to_datetime(panel["week_start"], format="mixed")
    duplicate = panel.duplicated(["region_group", "week_start"], keep=False)
    if duplicate.any():
        raise ValueError("Duplicate region-week rows are not allowed")
    if panel["rain_mm_day"].isna().any():
        raise ValueError("Missing regional rainfall in common panel")

    regions = sorted(panel["region_group"].unique())
    weights = pd.DataFrame({"region_group": regions})
    rain_by_week = panel.pivot(
        index="week_start", columns="region_group", values="rain_mm_day"
    ).sort_index()
    if rain_by_week.isna().any().any():
        raise ValueError("Missing regional rainfall in common panel")

    national = (
        panel.groupby("week_start", as_index=False, sort=True)[
            ["shipments", "volume_mt"]
        ]
        .sum()
        .sort_values("week_start")
        .reset_index(drop=True)
    )
    for metric in ("shipments", "volume_mt"):
        totals = panel.groupby("region_group", sort=True)[metric].sum().reindex(regions)
        total = totals.sum()
        if not pd.notna(total) or total <= 0:
            raise ValueError(f"Zero total {metric} weights are not allowed")
        metric_weights = totals / total
        weights[f"{metric}_weight"] = metric_weights.to_numpy()
        national[f"rain_{metric}"] = (
            rain_by_week.reindex(columns=regions)
            .mul(metric_weights, axis="columns")
            .sum(axis="columns")
            .to_numpy()
        )
    return national, weights


def _national_metric_panel(national_panel, metric):
    out = national_panel[
        ["week_start", f"rain_{metric}", metric]
    ].rename(columns={f"rain_{metric}": "rain_mm_day"})
    out["region_group"] = "Philippines weighted"
    other_metric = "volume_mt" if metric == "shipments" else "shipments"
    out[other_metric] = out[metric]
    return add_weekly_anomalies(out)


def calculate_national_lag_correlations(national_panel, max_lag=4):
    """Calculate national lags with each metric's corresponding weighted rain."""
    rows = []
    for metric in ("shipments", "volume_mt"):
        metric_panel = _national_metric_panel(national_panel, metric)
        result = calculate_lag_correlations(metric_panel, max_lag=max_lag)
        rows.append(result[result["metric"] == metric])
    return pd.concat(rows, ignore_index=True)


def calculate_national_monthly_correlations(national_panel):
    """Calculate national monthly robustness correlations by metric."""
    rows = []
    for metric in ("shipments", "volume_mt"):
        metric_panel = _national_metric_panel(national_panel, metric)
        result = calculate_monthly_correlations(metric_panel)
        rows.append(result[result["metric"] == metric])
    return pd.concat(rows, ignore_index=True)


def complete_monday_weeks(start_year, end_year):
    """Return complete Monday-Sunday weeks inside a >=5-year calendar range."""
    if end_year < start_year:
        raise ValueError("end_year must be >= start_year")
    if end_year - start_year + 1 < 5:
        raise ValueError("Analysis requires at least five calendar years")
    first_day = pd.Timestamp(year=start_year, month=1, day=1)
    first_monday = first_day + pd.Timedelta(days=(-first_day.weekday()) % 7)
    final_day = pd.Timestamp(year=end_year, month=12, day=31)
    last_monday = final_day - pd.Timedelta(days=final_day.weekday())
    if last_monday + pd.Timedelta(days=6) > final_day:
        last_monday -= pd.Timedelta(days=7)
    return pd.date_range(first_monday, last_monday, freq="W-MON")


def _validate_rainfall_data(frame, ports, start_year, end_year):
    required = {"date", "port_name", "region_group", "precipitation_mm"}
    missing_columns = sorted(required - set(frame.columns))
    if missing_columns:
        raise ValueError(
            f"Rainfall data missing columns: {', '.join(missing_columns)}"
        )
    out = frame.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce", format="mixed")
    if out["date"].isna().any():
        raise ValueError("Rainfall data contains invalid dates")
    outside_years = ~out["date"].dt.year.between(start_year, end_year)
    if outside_years.any():
        raise ValueError(
            f"Rainfall data contains dates outside {start_year}-{end_year}"
        )
    duplicate = out.duplicated(["port_name", "date"], keep=False)
    if duplicate.any():
        raise ValueError("Rainfall data contains duplicate port-date rows")
    expected_regions = {
        port_name: details["region_group"] for port_name, details in ports.items()
    }
    unknown = sorted(set(out["port_name"]) - set(expected_regions))
    if unknown:
        raise ValueError(f"Rainfall data contains unknown ports: {', '.join(unknown)}")
    mapped_regions = out["port_name"].map(expected_regions)
    if mapped_regions.ne(out["region_group"]).any():
        raise ValueError("Rainfall port-region mapping does not match rain.PORTS")
    return out


def load_rainfall_data(start_year, end_year, cache_path=None, ports=None):
    """Load validated daily rain from a supplied pickle or the existing loader."""
    ports = rain.PORTS if ports is None else ports
    if cache_path is not None:
        cache_path = Path(cache_path)
        if not cache_path.is_file():
            raise ValueError(f"Rain cache does not exist: {cache_path}")
        frame = pd.read_pickle(cache_path)
    else:
        frame = rain.load_historical_data_cached(
            f"{start_year}-01-01", f"{end_year}-12-31"
        )
    return _validate_rainfall_data(frame, ports, start_year, end_year)


def expected_port_counts(ports):
    """Return deterministic expected port counts by configured region."""
    rows = pd.DataFrame(
        [details["region_group"] for details in ports.values()],
        columns=["region_group"],
    )
    return (
        rows.groupby("region_group", as_index=False, sort=True)
        .size()
        .rename(columns={"size": "expected_ports"})
    )


def validate_rain_coverage(rain_weekly, regions, weeks, expected_ports):
    """Require every region-week to contain seven days and all configured ports."""
    grid = pd.MultiIndex.from_product(
        [list(regions), pd.DatetimeIndex(weeks)],
        names=["region_group", "week_start"],
    ).to_frame(index=False)
    checked = grid.merge(
        rain_weekly,
        on=["region_group", "week_start"],
        how="left",
        validate="one_to_one",
    ).merge(expected_ports, on="region_group", how="left", validate="many_to_one")
    failures = checked[
        checked["rain_mm_day"].isna()
        | checked["rain_days"].ne(7)
        | checked["min_ports"].ne(checked["expected_ports"])
    ]
    if not failures.empty:
        details = []
        for row in failures.itertuples():
            details.append(
                f"{row.region_group} {row.week_start:%Y-%m-%d}: "
                f"{row.rain_days} rain days, {row.min_ports}/{row.expected_ports} ports"
            )
        raise ValueError("Incomplete rainfall coverage: " + "; ".join(details))
    return (
        checked.groupby("region_group", as_index=False, sort=True)
        .agg(
            weeks=("week_start", "nunique"),
            min_rain_days=("rain_days", "min"),
            expected_ports=("expected_ports", "first"),
            min_ports=("min_ports", "min"),
        )
        .assign(expected_weeks=len(weeks))[
            [
                "region_group", "weeks", "expected_weeks", "min_rain_days",
                "expected_ports", "min_ports",
            ]
        ]
    )


def merge_weekly_panels(shipment_weekly, rain_weekly):
    """Merge complete weekly panels and identify any missing rainfall keys."""
    merged = shipment_weekly.merge(
        rain_weekly,
        on=["region_group", "week_start"],
        how="left",
        validate="one_to_one",
    )
    missing = merged[merged["rain_mm_day"].isna()]
    if not missing.empty:
        labels = ", ".join(
            f"{row.region_group} {row.week_start:%Y-%m-%d}"
            for row in missing.itertuples()
        )
        raise ValueError(f"Missing region-week rainfall: {labels}")
    return merged


RESULT_FILENAMES = {
    "weekly_lags": "weekly_lag_correlations.csv",
    "monthly": "monthly_correlations.csv",
    "coverage": "coverage.csv",
    "regional_weights": "regional_weights.csv",
}


def export_results(tables, output_dir):
    """Write the four documented analysis tables and return their paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, filename in RESULT_FILENAMES.items():
        path = output_dir / filename
        tables[key].to_csv(path, index=False)
        paths[key] = path
    return paths


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Analyze rainfall against Philippine nickel shipments."
    )
    parser.add_argument("--shipments-file", type=Path, required=True)
    parser.add_argument("--sheet", default="Raw_Cleaned")
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--rain-cache", type=Path)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("correlation_output")
    )
    return parser.parse_args(argv)


def _print_strongest_negative(weekly_lags, metric):
    candidates = weekly_lags[
        weekly_lags["metric"].eq(metric)
        & weekly_lags["pearson_anomaly"].notna()
        & weekly_lags["pearson_anomaly"].lt(0)
    ]
    label = f"Strongest negative de-seasonalized lag — {metric}"
    if candidates.empty:
        print(f"{label}: none")
        return
    strongest = candidates.loc[candidates["pearson_anomaly"].idxmin()]
    print(
        f"{label}: {strongest['scope']}, rain leads "
        f"{int(strongest['rain_leads_weeks'])} week(s), "
        f"r={strongest['pearson_anomaly']:.3f}, n={int(strongest['weeks'])}"
    )


def main(argv=None):
    args = parse_args(argv)
    weeks = complete_monday_weeks(args.start_year, args.end_year)
    regions = list(rain.REGION_ORDER)
    port_region_map = {
        port_name: details["region_group"]
        for port_name, details in rain.PORTS.items()
    }
    shipments = pd.read_excel(args.shipments_file, sheet_name=args.sheet)
    shipments = map_shipment_regions(shipments, port_region_map)
    shipment_weekly = build_shipment_weekly_panel(shipments, regions, weeks)

    rainfall = load_rainfall_data(
        args.start_year, args.end_year, args.rain_cache
    )
    rain_weekly = build_rain_weekly_panel(rainfall, weeks)
    coverage = validate_rain_coverage(
        rain_weekly, regions, weeks, expected_port_counts(rain.PORTS)
    )
    regional_panel = add_weekly_anomalies(
        merge_weekly_panels(shipment_weekly, rain_weekly)
    )

    regional_lags = calculate_lag_correlations(regional_panel)
    national_panel, regional_weights = build_national_panel(regional_panel)
    weekly_lags = pd.concat(
        [regional_lags, calculate_national_lag_correlations(national_panel)],
        ignore_index=True,
    )
    monthly = pd.concat(
        [
            calculate_monthly_correlations(regional_panel),
            calculate_national_monthly_correlations(national_panel),
        ],
        ignore_index=True,
    )
    tables = {
        "weekly_lags": weekly_lags,
        "monthly": monthly,
        "coverage": coverage,
        "regional_weights": regional_weights,
    }
    paths = export_results(tables, args.output_dir)

    _print_strongest_negative(weekly_lags, "shipments")
    _print_strongest_negative(weekly_lags, "volume_mt")
    print(
        f"Coverage: {len(regions)} regions, {len(weeks)} complete weeks, "
        f"{len(rain.PORTS)} configured ports"
    )
    print("Outputs: " + ", ".join(str(path) for path in paths.values()))
    return tables


if __name__ == "__main__":
    main()
