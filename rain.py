
import time
from datetime import date, timedelta
from typing import Any, Dict, List

import certifi
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import urllib3


# ============================================================
# Page config
# ============================================================

st.set_page_config(
    page_title="Philippine rain",
    page_icon="🌧️",
    layout="wide",
)


# ============================================================
# Port / loading area coordinates + latest region groups
# ============================================================

PORTS: Dict[str, Dict[str, Any]] = {
    # Surigao-Dinagat-Caraga
    "Adlay/Bislig": {"lat": 9.4115, "lon": 125.8607, "region_group": "Surigao-Dinagat-Caraga"},
    "Cagdianao - Kinalablaban Bay": {"lat": 9.503456, "lon": 125.8774, "region_group": "Surigao-Dinagat-Caraga"},
    "Claver (Taganito)": {"lat": 9.54824, "lon": 125.8160, "region_group": "Surigao-Dinagat-Caraga"},
    "Tubay": {"lat": 9.1500, "lon": 125.7300, "region_group": "Surigao-Dinagat-Caraga"},
    "Dinagat Island East": {"lat": 10.2170, "lon": 125.6000, "region_group": "Surigao-Dinagat-Caraga"},
    "Loreto and Looc Bay - Dinagat": {"lat": 10.3924, "lon": 125.5827, "region_group": "Surigao-Dinagat-Caraga"},
    "Laganan Bay": {"lat": 12.5742, "lon": 124.9842, "region_group": "Surigao-Dinagat-Caraga"},
    "Dahican": {"lat": 9.4000, "lon": 125.9000, "region_group": "Surigao-Dinagat-Caraga"},
    "Dinagat - West": {"lat": 10.1000, "lon": 125.5000, "region_group": "Surigao-Dinagat-Caraga"},
    "Melgar Bay - Dinagat": {"lat": 10.0750, "lon": 125.5700, "region_group": "Surigao-Dinagat-Caraga"},
    "Nonoc": {"lat": 9.8000, "lon": 125.6000, "region_group": "Surigao-Dinagat-Caraga"},
    "Surigao": {"lat": 9.7840, "lon": 125.4888, "region_group": "Surigao-Dinagat-Caraga"},
    "Hinituan&Talavera Islands": {"lat": 9.75655, "lon": 125.67130, "region_group": "Surigao-Dinagat-Caraga"},

    # Palawan
    "Rio Tuba": {"lat": 9.3727, "lon": 118.9596, "region_group": "Palawan"},
    "Sofronio Espanola": {"lat": 7.0000, "lon": 119.2000, "region_group": "Palawan"},
    "Berong - Palawan": {"lat": 9.4048, "lon": 118.2324, "region_group": "Palawan"},
    "Narra - East Palawan": {"lat": 9.7231, "lon": 118.7283, "region_group": "Palawan"},

    # Zambales-Luzon
    "Santa Cruz (Luzon)": {"lat": 15.9833, "lon": 120.9667, "region_group": "Zambales-Luzon"},
    "Masinloc": {"lat": 15.7583, "lon": 119.7633, "region_group": "Zambales-Luzon"},

    # Tawi-Tawi
    "Tawi-Tawi Nickel Ore Loading Area": {"lat": 5.0700, "lon": 119.7500, "region_group": "Tawi-Tawi"},
    "Tuhog-Tuhog Nickel Ore Loading Area": {"lat": 5.2267, "lon": 120.0478, "region_group": "Tawi-Tawi"},
    "Tumbagaan - Tawi-Tawi": {"lat": 5.2300, "lon": 119.7500, "region_group": "Tawi-Tawi"},
    "Lugus": {"lat": 5.7000, "lon": 120.8200, "region_group": "Tawi-Tawi"},

    # Eastern Samar
    "Homonhon Island": {"lat": 10.2775, "lon": 125.4750, "region_group": "Eastern Samar"},
    "Manicani": {"lat": 10.9903, "lon": 125.6360, "region_group": "Eastern Samar"},

    # Other-Check
    "Cebu": {"lat": 10.3157, "lon": 123.8854, "region_group": "Other-Check"},
    "Davao": {"lat": 7.1172, "lon": 125.6668, "region_group": "Other-Check"},
    "Dinapigue": {"lat": 16.6667, "lon": 122.2500, "region_group": "Other-Check"},
    "Gutalac": {"lat": 7.9833, "lon": 122.4000, "region_group": "Other-Check"},
    "Mati": {"lat": 6.9396, "lon": 126.2089, "region_group": "Other-Check"},
}

REGION_ORDER = [
    "Surigao-Dinagat-Caraga",
    "Palawan",
    "Zambales-Luzon",
    "Tawi-Tawi",
    "Eastern Samar",
    "Other-Check",
]

TIMEZONE = "Asia/Manila"


# ============================================================
# HTTP helper
# ============================================================

def request_json(
    url: str,
    params: Dict[str, Any],
    retries: int = 5,
    sleep_seconds: float = 1.5,
) -> Any:
    """
    Request JSON data with stronger retry logic.

    1) Try normal SSL verification using certifi.
    2) If SSL verification fails, retry with verify=False.
    3) Retry several times before giving up.
    """
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=60,
                verify=certifi.where(),
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.SSLError as exc:
            last_error = exc

            try:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                response = requests.get(
                    url,
                    params=params,
                    timeout=60,
                    verify=False,
                )
                response.raise_for_status()
                return response.json()

            except Exception as fallback_exc:
                last_error = fallback_exc
                time.sleep(sleep_seconds * attempt)

        except Exception as exc:
            last_error = exc
            time.sleep(sleep_seconds * attempt)

    raise RuntimeError(f"Request failed after {retries} retries. Last error: {last_error}")


def safe_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if result < -900:
        return None

    return result


# ============================================================
# Open-Meteo API functions
# ============================================================

def fetch_openmeteo_historical_daily(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
) -> Dict[str, Any]:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "precipitation_sum",
        "timezone": TIMEZONE,
    }
    return request_json(url, params)


def fetch_openmeteo_forecast_daily(
    lat: float,
    lon: float,
    forecast_days: int = 7,
) -> Dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "forecast_days": forecast_days,
        "timezone": TIMEZONE,
    }
    # Forecast should be fast. Use fewer retries than historical data,
    # otherwise one bad port can make the page wait too long.
    return request_json(url, params, retries=3, sleep_seconds=0.8)


def fetch_openmeteo_forecast_daily_batch(
    ports: Dict[str, Dict[str, Any]],
    forecast_days: int = 7,
) -> List[Dict[str, Any]]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": ",".join(str(port_info["lat"]) for port_info in ports.values()),
        "longitude": ",".join(str(port_info["lon"]) for port_info in ports.values()),
        "daily": "precipitation_sum",
        "forecast_days": forecast_days,
        "timezone": TIMEZONE,
    }
    data = request_json(url, params, retries=3, sleep_seconds=0.8)
    return data if isinstance(data, list) else [data]


def parse_openmeteo_daily(
    port_name: str,
    port_info: Dict[str, Any],
    api_data: Dict[str, Any],
    data_type: str,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    daily = api_data.get("daily", {})
    dates = daily.get("time", [])
    precipitation = daily.get("precipitation_sum", [])

    for date_value, precip_value in zip(dates, precipitation):
        precip = safe_float(precip_value)
        if precip is None:
            continue

        rows.append(
            {
                "source": "OpenMeteo",
                "data_type": data_type,
                "region_group": port_info["region_group"],
                "port_name": port_name,
                "latitude": port_info["lat"],
                "longitude": port_info["lon"],
                "date": date_value,
                "precipitation_mm": precip,
            }
        )

    return rows


def make_daily_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    columns = [
        "source",
        "data_type",
        "region_group",
        "port_name",
        "latitude",
        "longitude",
        "date",
        "precipitation_mm",
    ]

    df = pd.DataFrame(rows, columns=columns)

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df["precipitation_mm"] = pd.to_numeric(df["precipitation_mm"], errors="coerce")
        df = df.dropna(subset=["precipitation_mm"])

    return df


# ============================================================
# Cached data loading
# ============================================================

@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def load_historical_data_cached(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Load historical data once for the selected date range.

    Cache ttl = 12 hours.
    """
    all_rows: List[Dict[str, Any]] = []
    failed_ports: List[str] = []

    for port_name, port_info in PORTS.items():
        try:
            data = fetch_openmeteo_historical_daily(
                lat=port_info["lat"],
                lon=port_info["lon"],
                start_date=start_date,
                end_date=end_date,
            )
            all_rows.extend(parse_openmeteo_daily(port_name, port_info, data, "historical"))
            time.sleep(0.05)
        except Exception as exc:
            failed_ports.append(f"{port_name}: {exc}")
            continue

    df = make_daily_dataframe(all_rows)
    df.attrs["failed_ports"] = failed_ports
    return df


@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_forecast_data_today_cached(today_key: str, forecast_days: int = 7) -> pd.DataFrame:
    """
    Forecast is always based on current day + future 7 days.

    Faster version:
    - All port forecasts are fetched in one Open-Meteo batch request.
    - today_key is only used to refresh the cache once per day.
    - It does NOT come from the sidebar date range.
    """
    all_rows: List[Dict[str, Any]] = []
    failed_ports: List[str] = []

    try:
        forecasts = fetch_openmeteo_forecast_daily_batch(PORTS, forecast_days)
        if len(forecasts) != len(PORTS):
            raise ValueError(
                f"Expected {len(PORTS)} forecast locations, received {len(forecasts)}."
            )

        for (port_name, port_info), forecast in zip(PORTS.items(), forecasts):
            all_rows.extend(parse_openmeteo_daily(port_name, port_info, forecast, "forecast"))
    except Exception as exc:
        failed_ports = [f"{port_name}: {exc}" for port_name in PORTS]

    df = make_daily_dataframe(all_rows)
    df.attrs["failed_ports"] = failed_ports
    return df


# ============================================================
# Aggregation
# ============================================================

def historical_monthly_region_total(df_daily: pd.DataFrame) -> pd.DataFrame:
    if df_daily.empty:
        return pd.DataFrame()

    df = df_daily.copy()
    df["month"] = df["date"].dt.to_period("M").astype(str)

    region_monthly = (
        df.groupby(["region_group", "month"], as_index=False)
        .agg(
            port_count=("port_name", "nunique"),
            observation_days=("date", "nunique"),
            regional_total_precipitation_mm=("precipitation_mm", "sum"),
        )
    )

    region_monthly["regional_total_precipitation_mm"] = region_monthly[
        "regional_total_precipitation_mm"
    ].round(2)

    region_monthly["region_group"] = pd.Categorical(
        region_monthly["region_group"],
        categories=REGION_ORDER,
        ordered=True,
    )
    region_monthly = region_monthly.sort_values(["region_group", "month"])
    region_monthly["region_group"] = region_monthly["region_group"].astype(str)

    return region_monthly


def forecast_daily_region_total(df_daily: pd.DataFrame) -> pd.DataFrame:
    if df_daily.empty:
        return pd.DataFrame()

    df = df_daily.copy()

    region_daily = (
        df.groupby(["region_group", "date"], as_index=False)
        .agg(
            port_count=("port_name", "nunique"),
            regional_total_precipitation_mm=("precipitation_mm", "sum"),
        )
    )

    region_daily["regional_total_precipitation_mm"] = region_daily[
        "regional_total_precipitation_mm"
    ].round(2)

    region_daily["date_label"] = region_daily["date"].dt.strftime("%Y-%m-%d")
    region_daily["region_group"] = pd.Categorical(
        region_daily["region_group"],
        categories=REGION_ORDER,
        ordered=True,
    )
    region_daily = region_daily.sort_values(["region_group", "date"])
    region_daily["region_group"] = region_daily["region_group"].astype(str)

    return region_daily


def forecast_total_by_region(df_forecast_region_daily: pd.DataFrame) -> pd.DataFrame:
    if df_forecast_region_daily.empty:
        return pd.DataFrame()

    summary = (
        df_forecast_region_daily.groupby("region_group", as_index=False)
        .agg(
            forecast_days=("date", "nunique"),
            port_count=("port_count", "max"),
            total_7d_precipitation_mm=("regional_total_precipitation_mm", "sum"),
        )
    )

    summary["total_7d_precipitation_mm"] = summary["total_7d_precipitation_mm"].round(2)
    summary["region_group"] = pd.Categorical(
        summary["region_group"],
        categories=REGION_ORDER,
        ordered=True,
    )
    summary = summary.sort_values("region_group")
    summary["region_group"] = summary["region_group"].astype(str)

    return summary


def expected_port_count_by_region() -> pd.DataFrame:
    rows = []
    for region in REGION_ORDER:
        expected_ports = [
            port_name
            for port_name, port_info in PORTS.items()
            if port_info["region_group"] == region
        ]
        rows.append(
            {
                "region_group": region,
                "expected_port_count": len(expected_ports),
                "expected_ports": "; ".join(expected_ports),
            }
        )
    return pd.DataFrame(rows)


def actual_port_count_by_region(df_daily: pd.DataFrame) -> pd.DataFrame:
    expected = expected_port_count_by_region()

    if df_daily.empty:
        expected["actual_port_count"] = 0
        expected["missing_port_count"] = expected["expected_port_count"]
        expected["actual_ports"] = ""
        return expected

    actual = (
        df_daily.groupby("region_group", as_index=False)
        .agg(
            actual_port_count=("port_name", "nunique"),
            actual_ports=("port_name", lambda x: "; ".join(sorted(set(x)))),
        )
    )

    result = expected.merge(actual, on="region_group", how="left")
    result["actual_port_count"] = result["actual_port_count"].fillna(0).astype(int)
    result["actual_ports"] = result["actual_ports"].fillna("")
    result["missing_port_count"] = result["expected_port_count"] - result["actual_port_count"]

    return result[
        [
            "region_group",
            "expected_port_count",
            "actual_port_count",
            "missing_port_count",
            "actual_ports",
            "expected_ports",
        ]
    ]


# ============================================================
# Charts
# ============================================================

def show_historical_region_charts(df_monthly: pd.DataFrame, selected_regions: List[str]) -> None:
    if df_monthly.empty:
        st.warning("No historical monthly data available.")
        return

    chart_df = df_monthly[df_monthly["region_group"].isin(selected_regions)].copy()

    for region in selected_regions:
        region_df = chart_df[chart_df["region_group"] == region].copy()
        if region_df.empty:
            continue

        st.subheader(region)

        col1, col2 = st.columns(2)

        with col1:
            fig_bar = px.bar(
                region_df,
                x="month",
                y="regional_total_precipitation_mm",
                title=f"{region} monthly rainfall - bar",
                labels={
                    "month": "Month",
                    "regional_total_precipitation_mm": "Rainfall (mm)",
                },
            )
            fig_bar.update_layout(
                height=360,
                margin=dict(l=20, r=20, t=60, b=20),
                xaxis_type="category",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col2:
            fig_line = px.line(
                region_df,
                x="month",
                y="regional_total_precipitation_mm",
                markers=True,
                title=f"{region} monthly rainfall - line",
                labels={
                    "month": "Month",
                    "regional_total_precipitation_mm": "Rainfall (mm)",
                },
            )
            fig_line.update_layout(
                height=360,
                margin=dict(l=20, r=20, t=60, b=20),
                xaxis_type="category",
            )
            st.plotly_chart(fig_line, use_container_width=True)


def show_forecast_section(df_forecast_region_daily: pd.DataFrame, selected_regions: List[str]) -> None:
    if df_forecast_region_daily.empty:
        st.warning("No forecast data available.")
        return

    chart_df = df_forecast_region_daily[
        df_forecast_region_daily["region_group"].isin(selected_regions)
    ].copy()

    st.subheader("Future 7 days daily rainfall by region")

    fig = px.bar(
        chart_df,
        x="date_label",
        y="regional_total_precipitation_mm",
        color="region_group",
        barmode="group",
        title="Future 7 days daily rainfall by region",
        labels={
            "date_label": "Date",
            "regional_total_precipitation_mm": "Rainfall (mm)",
            "region_group": "Region",
        },
    )
    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis_type="category",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Future 7 days total rainfall summary")
    summary_df = forecast_total_by_region(chart_df)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    fig_total = px.bar(
        summary_df,
        x="region_group",
        y="total_7d_precipitation_mm",
        title="Future 7 days total rainfall by region",
        labels={
            "region_group": "Region",
            "total_7d_precipitation_mm": "Rainfall (mm)",
        },
    )
    fig_total.update_layout(
        height=420,
        margin=dict(l=20, r=20, t=60, b=20),
        xaxis_type="category",
    )
    st.plotly_chart(fig_total, use_container_width=True)


# ============================================================
# Streamlit UI
# ============================================================

def main() -> None:
    today = date.today()
    default_start = max(date(today.year, 1, 1), today - timedelta(days=365))
    default_end = today

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Select page", ["Philippine rain"])

    st.sidebar.divider()
    st.sidebar.subheader("Historical settings")

    start_date = st.sidebar.date_input(
        "Historical start date",
        value=default_start,
        max_value=today,
    )

    end_date = st.sidebar.date_input(
        "Historical end date",
        value=default_end,
        max_value=today,
    )

    selected_regions = st.sidebar.multiselect(
        "Regions",
        options=REGION_ORDER,
        default=REGION_ORDER,
    )

    st.sidebar.caption("Historical date selectors are capped at today.")
    st.sidebar.caption("Forecast is always today + future 7 days.")
    st.sidebar.caption("Data source: Open-Meteo API. Unit: mm.")

    if page == "Philippine rain":
        st.title("Philippine rain")
        st.caption("Open-Meteo rainfall dashboard for Philippine nickel ore loading regions.")

        if not selected_regions:
            st.warning("Please select at least one region in the sidebar.")
            return

        if pd.to_datetime(start_date) > pd.to_datetime(end_date):
            st.error("Historical start date must be earlier than end date.")
            return

        # Historical section
        st.header("1. Historical monthly rainfall by region")

        with st.spinner("Loading historical Open-Meteo rainfall data..."):
            df_hist_daily = load_historical_data_cached(
                start_date=pd.to_datetime(start_date).strftime("%Y-%m-%d"),
                end_date=pd.to_datetime(end_date).strftime("%Y-%m-%d"),
            )

        failed_hist_ports = df_hist_daily.attrs.get("failed_ports", [])
        if failed_hist_ports:
            with st.expander(f"Historical data warning: {len(failed_hist_ports)} port requests failed"):
                st.write("\n".join(failed_hist_ports))

        df_hist_monthly = historical_monthly_region_total(df_hist_daily)

        if not df_hist_monthly.empty:
            st.dataframe(
                df_hist_monthly[df_hist_monthly["region_group"].isin(selected_regions)],
                use_container_width=True,
                hide_index=True,
            )

        show_historical_region_charts(df_hist_monthly, selected_regions)

        # Forecast section
        st.header("2. Future 7 days rainfall")
        st.caption(f"Forecast is fixed from today: {today.strftime('%Y-%m-%d')}. It is not affected by historical date selections.")
        st.caption("Forecast locations are loaded in one batch request to improve speed.")

        with st.spinner("Loading today's Open-Meteo 7-day forecast..."):
            df_forecast_daily = load_forecast_data_today_cached(
                today_key=today.strftime("%Y-%m-%d"),
                forecast_days=7,
            )

        failed_forecast_ports = df_forecast_daily.attrs.get("failed_ports", [])
        if failed_forecast_ports:
            with st.expander(f"Forecast data warning: {len(failed_forecast_ports)} port requests failed"):
                st.write("\n".join(failed_forecast_ports))

        with st.expander("Forecast port coverage by region"):
            coverage_df = actual_port_count_by_region(df_forecast_daily)
            st.dataframe(coverage_df, use_container_width=True, hide_index=True)

        df_forecast_region_daily = forecast_daily_region_total(df_forecast_daily)
        show_forecast_section(df_forecast_region_daily, selected_regions)


if __name__ == "__main__":
    main()
