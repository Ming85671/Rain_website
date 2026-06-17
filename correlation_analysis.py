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

    unmapped = sorted(
        out.loc[out["region_group"].isna(), "load_port"].drop_duplicates()
    )
    if unmapped:
        raise ValueError(f"Unmapped shipment ports: {', '.join(unmapped)}")

    return out


def monday_start(values):
    """Convert date-like values to normalized starts of Monday-based weeks."""
    dates = pd.to_datetime(values, errors="coerce", format="mixed")
    return (dates - pd.to_timedelta(dates.dt.weekday, unit="D")).dt.normalize()


def build_shipment_weekly_panel(shipments, regions, weeks):
    """Aggregate shipments onto a complete supplied region-week grid."""
    out = shipments.copy()
    out["load_start_date"] = pd.to_datetime(
        out["load_start_date"], errors="coerce", format="mixed"
    )
    out["voy_intake_mt"] = pd.to_numeric(
        out["voy_intake_mt"], errors="coerce"
    ).fillna(0)
    out = out.dropna(subset=["load_start_date", "region_group", "vsl_name"])
    out["week_start"] = monday_start(out["load_start_date"])

    index = pd.MultiIndex.from_product(
        [regions, weeks], names=["region_group", "week_start"]
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
