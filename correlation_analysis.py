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
