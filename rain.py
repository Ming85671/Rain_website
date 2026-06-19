
import ipaddress
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse, urlunparse

import certifi
import correlation_analysis as correlation
import mysql.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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

MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_LABEL_MAP = {index: month for index, month in enumerate(MONTH_ORDER, start=1)}
MONTH_TICK_VALUES = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335]
YEAR_COLOR_OVERRIDES = {"2026": "#0B5FFF"}
FOCUS_YEAR_LABEL = "2026"
FOCUS_YEAR_LINE_WIDTH = 3.5
COMPARISON_YEAR_LINE_WIDTH = 1.8
COMPARISON_YEAR_OPACITY = 0.6
YEAR_COLOR_SEQUENCE = [
    "#0B5FFF",
    "#D97706",
    "#059669",
    "#7C3AED",
    "#DC2626",
    "#0891B2",
    "#9333EA",
    "#4B5563",
]

TIMEZONE = "Asia/Manila"
FORECAST_CACHE_VERSION = "2026-06-16-batch-fallback"
HISTORICAL_CACHE_VERSION = "2026-06-16-batch-fallback"
CORRELATION_DATA_DIR = Path(__file__).with_name("correlation_output")
CORRELATION_BLUE = "#0B5FFF"
CORRELATION_TEAL = "#4B9AA6"
CORRELATION_RED = "#C96A63"
CORRELATION_SIDEBAR_CAPTION = "Live refresh · complete weeks only"
CORRELATION_METRICS = {
    "Shipment count": {"key": "shipments", "noun": "shipment count"},
    "Shipment volume (mt)": {"key": "volume_mt", "noun": "shipment volume"},
}


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
# DNS fallback helpers
# ============================================================

def resolve_hostname_doh(hostname: str) -> str:
    """Resolve hostname using DNS-over-HTTPS. Only used when normal DNS fails."""
    last_error: Exception | None = None

    for verify_ssl in [True, False]:
        try:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(
                "https://1.1.1.1/dns-query",
                params={"name": hostname, "type": "A"},
                headers={"accept": "application/dns-json"},
                timeout=15,
                verify=certifi.where() if verify_ssl else False,
            )
            response.raise_for_status()

            for answer in response.json().get("Answer", []):
                candidate = answer.get("data", "")
                try:
                    ipaddress.ip_address(candidate)
                except ValueError:
                    continue
                return candidate

        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(f"DNS-over-HTTPS did not return an IP address for {hostname}. Last error: {last_error}")


def request_json_via_ip(url: str, params: Dict[str, Any]) -> Any:
    """Request an API through resolved IP, preserving original hostname with Host header."""
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    if not hostname:
        raise RuntimeError(f"Cannot determine hostname from URL: {url}")

    ip_address = resolve_hostname_doh(hostname)
    ip_url = urlunparse(parsed_url._replace(netloc=ip_address))

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    response = requests.get(
        ip_url,
        params=params,
        headers={"Host": hostname},
        timeout=60,
        verify=False,
    )
    response.raise_for_status()
    return response.json()


def request_openmeteo_with_dns_fallback(
    url: str,
    params: Dict[str, Any],
    retries: int = 3,
    sleep_seconds: float = 0.8,
) -> Any:
    """Normal Open-Meteo request first; if DNS fails, try DNS-over-HTTPS + IP fallback."""
    try:
        return request_json(url, params, retries=retries, sleep_seconds=sleep_seconds)
    except RuntimeError as exc:
        if "NameResolutionError" not in str(exc):
            raise
        return request_json_via_ip(url, params)


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
    return request_openmeteo_with_dns_fallback(url, params, retries=3, sleep_seconds=0.8)


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
    return request_openmeteo_with_dns_fallback(url, params, retries=3, sleep_seconds=0.8)


def fetch_openmeteo_historical_daily_batch(
    ports: Dict[str, Dict[str, Any]],
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Try to fetch all historical locations in one Open-Meteo request."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": ",".join(str(port_info["lat"]) for port_info in ports.values()),
        "longitude": ",".join(str(port_info["lon"]) for port_info in ports.values()),
        "start_date": start_date,
        "end_date": end_date,
        "daily": "precipitation_sum",
        "timezone": TIMEZONE,
    }
    data = request_openmeteo_with_dns_fallback(url, params, retries=3, sleep_seconds=0.8)
    return data if isinstance(data, list) else [data]


def fetch_openmeteo_forecast_daily_batch(
    ports: Dict[str, Dict[str, Any]],
    forecast_days: int = 7,
) -> List[Dict[str, Any]]:
    """Try to fetch all forecast locations in one Open-Meteo request."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": ",".join(str(port_info["lat"]) for port_info in ports.values()),
        "longitude": ",".join(str(port_info["lon"]) for port_info in ports.values()),
        "daily": "precipitation_sum",
        "forecast_days": forecast_days,
        "timezone": TIMEZONE,
    }
    data = request_openmeteo_with_dns_fallback(url, params, retries=3, sleep_seconds=0.8)
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

def fetch_one_historical_port(port_name: str, port_info: Dict[str, Any], start_date: str, end_date: str) -> List[Dict[str, Any]]:
    data = fetch_openmeteo_historical_daily(
        lat=port_info["lat"],
        lon=port_info["lon"],
        start_date=start_date,
        end_date=end_date,
    )
    return parse_openmeteo_daily(port_name, port_info, data, "historical")


def fetch_one_forecast_port(port_name: str, port_info: Dict[str, Any], forecast_days: int) -> List[Dict[str, Any]]:
    data = fetch_openmeteo_forecast_daily(
        lat=port_info["lat"],
        lon=port_info["lon"],
        forecast_days=forecast_days,
    )
    return parse_openmeteo_daily(port_name, port_info, data, "forecast")


def fetch_historical_concurrently(start_date: str, end_date: str) -> tuple[List[Dict[str, Any]], List[str]]:
    all_rows: List[Dict[str, Any]] = []
    failed_ports: List[str] = []
    max_workers = min(8, len(PORTS))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_port = {
            executor.submit(fetch_one_historical_port, port_name, port_info, start_date, end_date): port_name
            for port_name, port_info in PORTS.items()
        }
        for future in as_completed(future_to_port):
            port_name = future_to_port[future]
            try:
                all_rows.extend(future.result())
            except Exception as exc:
                failed_ports.append(f"{port_name}: {exc}")

    return all_rows, failed_ports


def fetch_forecast_concurrently(forecast_days: int) -> tuple[List[Dict[str, Any]], List[str]]:
    all_rows: List[Dict[str, Any]] = []
    failed_ports: List[str] = []
    max_workers = min(8, len(PORTS))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_port = {
            executor.submit(fetch_one_forecast_port, port_name, port_info, forecast_days): port_name
            for port_name, port_info in PORTS.items()
        }
        for future in as_completed(future_to_port):
            port_name = future_to_port[future]
            try:
                all_rows.extend(future.result())
            except Exception as exc:
                failed_ports.append(f"{port_name}: {exc}")

    return all_rows, failed_ports


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def load_historical_data_cached(
    start_date: str,
    end_date: str,
    cache_version: str = HISTORICAL_CACHE_VERSION,
) -> pd.DataFrame:
    """
    Load historical data.

    Fast path: one Open-Meteo batch request for all locations.
    Fallback: if batch fails or returns wrong location count, fetch ports concurrently.
    """
    _ = cache_version
    all_rows: List[Dict[str, Any]] = []
    failed_ports: List[str] = []

    try:
        historical_results = fetch_openmeteo_historical_daily_batch(PORTS, start_date, end_date)
        if len(historical_results) != len(PORTS):
            raise ValueError(f"Expected {len(PORTS)} historical locations, received {len(historical_results)}.")

        for (port_name, port_info), historical in zip(PORTS.items(), historical_results):
            all_rows.extend(parse_openmeteo_daily(port_name, port_info, historical, "historical"))

    except Exception as batch_exc:
        all_rows, failed_ports = fetch_historical_concurrently(start_date, end_date)
        if failed_ports:
            failed_ports.insert(0, f"Batch historical request failed first: {batch_exc}")

    df = make_daily_dataframe(all_rows)
    df.attrs["failed_ports"] = failed_ports
    return df


@st.cache_data(ttl=60 * 30, show_spinner=False)
def load_forecast_data_today_cached(
    today_key: str,
    forecast_days: int = 7,
    cache_version: str = FORECAST_CACHE_VERSION,
) -> pd.DataFrame:
    """
    Forecast is always based on current day + future 7 days.

    Fast path: one Open-Meteo batch request for all locations.
    Fallback: if batch fails or returns wrong location count, fetch ports concurrently.
    """
    _ = today_key
    _ = cache_version
    all_rows: List[Dict[str, Any]] = []
    failed_ports: List[str] = []

    try:
        forecasts = fetch_openmeteo_forecast_daily_batch(PORTS, forecast_days)
        if len(forecasts) != len(PORTS):
            raise ValueError(f"Expected {len(PORTS)} forecast locations, received {len(forecasts)}.")

        for (port_name, port_info), forecast in zip(PORTS.items(), forecasts):
            all_rows.extend(parse_openmeteo_daily(port_name, port_info, forecast, "forecast"))

    except Exception as batch_exc:
        all_rows, failed_ports = fetch_forecast_concurrently(forecast_days)
        if failed_ports:
            failed_ports.insert(0, f"Batch forecast request failed first: {batch_exc}")

    df = make_daily_dataframe(all_rows)
    df.attrs["failed_ports"] = failed_ports
    return df


# ============================================================
# Aggregation
# ============================================================

def historical_monthly_region_total(df_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Historical region monthly summary.

    The chart metric is a 7-day average rainfall equivalent:

        seven_day_avg_precipitation_mm = regional_total_precipitation_mm / observation_days * 7

    This makes different months easier to compare because Feb/Mar/Apr have different day counts.
    """
    if df_daily.empty:
        return pd.DataFrame()

    df = df_daily.copy()
    df["year"] = df["date"].dt.year
    df["month_num"] = df["date"].dt.month
    df["month"] = df["month_num"].map(MONTH_LABEL_MAP)

    region_monthly = (
        df.groupby(["region_group", "year", "month_num", "month"], as_index=False)
        .agg(
            port_count=("port_name", "nunique"),
            observation_days=("date", "nunique"),
            regional_total_precipitation_mm=("precipitation_mm", "sum"),
        )
    )

    region_monthly["regional_total_precipitation_mm"] = region_monthly[
        "regional_total_precipitation_mm"
    ].round(2)

    region_monthly["seven_day_avg_precipitation_mm"] = (
        region_monthly["regional_total_precipitation_mm"]
        / region_monthly["observation_days"].replace(0, pd.NA)
        * 7
    ).round(2)

    region_monthly["year_label"] = region_monthly["year"].astype(str)

    region_monthly["region_group"] = pd.Categorical(
        region_monthly["region_group"],
        categories=REGION_ORDER,
        ordered=True,
    )
    region_monthly["month"] = pd.Categorical(
        region_monthly["month"],
        categories=MONTH_ORDER,
        ordered=True,
    )
    region_monthly = region_monthly.sort_values(["region_group", "year", "month_num"])
    region_monthly["region_group"] = region_monthly["region_group"].astype(str)
    region_monthly["month"] = region_monthly["month"].astype(str)

    return region_monthly


def historical_seven_day_region_average(
    df_daily: pd.DataFrame,
    selected_years: List[int] | None = None,
) -> pd.DataFrame:
    if df_daily.empty:
        return pd.DataFrame()

    df = df_daily.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["precipitation_mm"] = pd.to_numeric(df["precipitation_mm"], errors="coerce")
    df = df.dropna(subset=["date", "precipitation_mm"])

    if df.empty:
        return pd.DataFrame()

    df["year"] = df["date"].dt.year

    if selected_years is not None:
        df = df[df["year"].isin(selected_years)]

    if df.empty:
        return pd.DataFrame()

    year_start = pd.to_datetime(df["year"].astype(str) + "-01-01")
    df["window_sort"] = (((df["date"] - year_start).dt.days // 7) * 7) + 1
    df["window_start"] = year_start + pd.to_timedelta(df["window_sort"] - 1, unit="D")

    december_tail = (df["date"].dt.month == 12) & (df["date"].dt.day >= 24)
    df.loc[december_tail, "window_start"] = pd.to_datetime(
        df.loc[december_tail, "year"].astype(str) + "-12-24"
    )
    df.loc[december_tail, "window_sort"] = (
        (df.loc[december_tail, "window_start"] - year_start.loc[december_tail]).dt.days + 1
    )

    df["month"] = df["window_start"].dt.strftime("%b")
    df["month_number"] = df["window_start"].dt.month

    region_window = (
        df.groupby(
            [
                "region_group",
                "year",
                "month",
                "month_number",
                "window_sort",
                "window_start",
            ],
            as_index=False,
        )
        .agg(
            window_end=("date", "max"),
            port_count=("port_name", "nunique"),
            observation_days=("date", "nunique"),
            average_precipitation_mm=("precipitation_mm", "mean"),
        )
    )

    region_window["average_precipitation_mm"] = region_window[
        "average_precipitation_mm"
    ].round(2)
    region_window["window_label"] = (
        region_window["window_start"].dt.strftime("%b %-d")
        + "-"
        + region_window["window_end"].dt.strftime("%-d")
    )
    region_window["hover_label"] = (
        region_window["window_start"].dt.strftime("%Y-%m-%d")
        + " to "
        + region_window["window_end"].dt.strftime("%Y-%m-%d")
    )

    region_window["region_group"] = pd.Categorical(
        region_window["region_group"],
        categories=REGION_ORDER,
        ordered=True,
    )
    region_window = region_window.sort_values(["region_group", "year", "window_sort"])
    region_window["region_group"] = region_window["region_group"].astype(str)
    region_window["year_label"] = region_window["year"].astype(str)

    return region_window


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


def rainfall_axis_max(values: Any, step: int = 5) -> int:
    numeric_values = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    if numeric_values.empty:
        return step

    highest_value = float(numeric_values.max())
    axis_max = math.ceil(highest_value / step) * step
    if axis_max <= highest_value:
        axis_max += step

    return max(step, int(axis_max))


def year_color_map(years: List[int]) -> Dict[str, str]:
    color_map: Dict[str, str] = {}
    reserved_colors = set(YEAR_COLOR_OVERRIDES.values())
    next_color_index = 0

    for year in sorted(years):
        year_label = str(year)
        if year_label in YEAR_COLOR_OVERRIDES:
            color_map[year_label] = YEAR_COLOR_OVERRIDES[year_label]
            continue

        while (
            YEAR_COLOR_SEQUENCE[next_color_index % len(YEAR_COLOR_SEQUENCE)] in color_map.values()
            or YEAR_COLOR_SEQUENCE[next_color_index % len(YEAR_COLOR_SEQUENCE)] in reserved_colors
        ):
            next_color_index += 1
        color_map[year_label] = YEAR_COLOR_SEQUENCE[next_color_index % len(YEAR_COLOR_SEQUENCE)]
        next_color_index += 1

    return color_map


def apply_historical_rainfall_axes(fig: Any, y_axis_max: int) -> None:
    grid_color = "#E5E7EB"
    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor="white",
        xaxis=dict(
            tickmode="array",
            tickvals=MONTH_TICK_VALUES,
            ticktext=MONTH_ORDER,
            showgrid=False,
        ),
        yaxis=dict(
            range=[0, y_axis_max],
            tick0=0,
            dtick=5,
            showgrid=True,
            gridcolor=grid_color,
            zeroline=False,
        ),
        shapes=[
            dict(
                type="line",
                xref="paper",
                yref="y",
                x0=0,
                x1=1,
                y0=0,
                y1=0,
                line=dict(color=grid_color, width=1),
                layer="below",
            ),
            dict(
                type="line",
                xref="paper",
                yref="y",
                x0=0,
                x1=1,
                y0=y_axis_max,
                y1=y_axis_max,
                line=dict(color=grid_color, width=1),
                layer="below",
            )
        ],
    )


def apply_year_trace_styles(fig: Any) -> None:
    for trace in fig.data:
        if str(trace.name) == FOCUS_YEAR_LABEL:
            trace.update(line=dict(width=FOCUS_YEAR_LINE_WIDTH), opacity=1.0)
        else:
            trace.update(line=dict(width=COMPARISON_YEAR_LINE_WIDTH), opacity=COMPARISON_YEAR_OPACITY)


# ============================================================
# Charts
# ============================================================

def show_historical_region_charts(
    df_seven_day: pd.DataFrame,
    selected_regions: List[str],
    selected_years: List[int],
) -> None:
    if df_seven_day.empty:
        st.warning("No historical 7-day average data available.")
        return

    chart_df = df_seven_day[df_seven_day["region_group"].isin(selected_regions)].copy()
    primary_year = max(selected_years)
    color_map = year_color_map(selected_years)

    for region in selected_regions:
        region_df = chart_df[chart_df["region_group"] == region].copy()
        if region_df.empty:
            continue

        primary_year_df = region_df[region_df["year"] == primary_year].copy()
        y_axis_max = rainfall_axis_max(region_df["average_precipitation_mm"])
        st.subheader(region)

        fig_line = px.line(
            region_df,
            x="window_sort",
            y="average_precipitation_mm",
            color="year_label",
            color_discrete_map=color_map,
            markers=False,
            category_orders={"year_label": [str(year) for year in selected_years]},
            title=f"{region} 7-day average rainfall - line",
            hover_data={
                "hover_label": True,
                "window_sort": False,
                "average_precipitation_mm": ":.2f",
                "port_count": True,
                "observation_days": True,
            },
            labels={
                "window_sort": "Month",
                "average_precipitation_mm": "7-day average rainfall (mm/day)",
                "year_label": "Year",
                "hover_label": "Window",
                "port_count": "Ports",
                "observation_days": "Days",
            },
        )
        apply_year_trace_styles(fig_line)
        apply_historical_rainfall_axes(fig_line, y_axis_max)
        st.plotly_chart(fig_line, use_container_width=True)

        if primary_year_df.empty:
            st.info(f"No {primary_year} 7-day average data available for {region}.")
            continue

        fig_bar = px.bar(
            primary_year_df,
            x="window_sort",
            y="average_precipitation_mm",
            title=f"{region} 7-day average rainfall - bar ({primary_year})",
            hover_data={
                "hover_label": True,
                "window_sort": False,
                "average_precipitation_mm": ":.2f",
                "port_count": True,
                "observation_days": True,
            },
            labels={
                "window_sort": "Month",
                "average_precipitation_mm": "7-day average rainfall (mm/day)",
                "hover_label": "Window",
                "port_count": "Ports",
                "observation_days": "Days",
            },
        )
        fig_bar.update_traces(marker_color=color_map.get(str(primary_year), "#0B5FFF"))
        apply_historical_rainfall_axes(fig_bar, y_axis_max)
        st.plotly_chart(fig_bar, use_container_width=True)


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
        labels={
            "region_group": "Region",
            "total_7d_precipitation_mm": "Rainfall (mm)",
        },
    )
    fig_total.update_layout(
        width=430,
        height=390,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis_type="category",
    )
    st.markdown("**Future 7 days total rainfall by region**")
    _, chart_column, _ = st.columns([2, 2, 2])
    with chart_column:
        st.plotly_chart(fig_total, use_container_width=False)


# ============================================================
# Rainfall-shipment correlation page
# ============================================================


@dataclass(frozen=True)
class CorrelationPageData:
    weekly: pd.DataFrame
    monthly: pd.DataFrame
    rolling_monthly: pd.DataFrame
    coverage: pd.DataFrame
    weights: pd.DataFrame
    source: str
    warning: str | None = None

@st.cache_data(show_spinner=False)
def load_correlation_outputs(data_dir: Path = CORRELATION_DATA_DIR):
    """Load the verified aggregate outputs committed for Streamlit Cloud."""
    filenames = [
        "weekly_lag_correlations.csv",
        "monthly_correlations.csv",
        "rolling_monthly_correlations.csv",
        "coverage.csv",
        "regional_weights.csv",
    ]
    missing = [name for name in filenames if not (data_dir / name).exists()]
    if missing:
        raise FileNotFoundError(
            "Missing correlation output files: " + ", ".join(missing)
        )

    tables = [pd.read_csv(data_dir / name) for name in filenames]
    weekly, monthly, rolling_monthly, coverage, weights = tables
    for frame in [weekly, monthly]:
        frame["analysis_start"] = frame["analysis_start"].astype(str)
        frame["analysis_end"] = frame["analysis_end"].astype(str)
    rolling_monthly["month"] = rolling_monthly["month"].astype(str)
    return weekly, monthly, rolling_monthly, coverage, weights


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def load_live_shipments(config_items) -> pd.DataFrame:
    """Load the live Philippine nickel shipment inputs from MySQL."""
    required = [
        "load_start_date",
        "load_port",
        "vsl_name",
        "voy_intake_mt",
    ]
    query = """
        SELECT load_start_date, load_port, vsl_name, voy_intake_mt
        FROM axs
        WHERE load_country = 'Philippines'
          AND commodity LIKE '%NICKEL%'
        ORDER BY load_start_date
    """
    connection = mysql.connector.connect(**dict(config_items))
    try:
        frame = pd.read_sql(query, connection)
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(
                "Live shipment data missing columns: " + ", ".join(missing)
            )
        return frame[required].copy()
    finally:
        connection.close()


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def load_live_correlation_outputs(config_items, today_key: str):
    """Calculate live correlation outputs through a conservative complete week."""
    shipments = load_live_shipments(config_items)
    final_week = correlation.latest_analysis_week(
        shipments,
        today=today_key,
    )
    weeks = correlation.complete_monday_weeks_through(2021, final_week)
    final_day = final_week + pd.Timedelta(days=6)
    rainfall = load_historical_data_cached(
        "2021-01-01",
        final_day.strftime("%Y-%m-%d"),
        cache_version=f"live-correlation-{final_day:%Y-%m-%d}",
    )
    rainfall = correlation._validate_rainfall_data(
        rainfall,
        PORTS,
        2021,
        final_day.year,
    )
    tables = correlation.calculate_correlation_tables(
        shipments,
        rainfall,
        regions=REGION_ORDER,
        ports=PORTS,
        weeks=weeks,
        weight_baseline_end="2025-12-31",
    )
    return (
        tables["weekly_lags"],
        tables["monthly"],
        tables["rolling_monthly"],
        tables["coverage"],
        tables["regional_weights"],
    )


def resolve_correlation_data(
    database_config,
    today_key: str | None = None,
) -> CorrelationPageData:
    """Prefer validated live results and fall back to the committed snapshot."""
    if today_key is None:
        today_key = date.today().isoformat()

    if database_config:
        try:
            config_items = tuple(sorted(dict(database_config).items()))
            weekly, monthly, rolling_monthly, coverage, weights = load_live_correlation_outputs(
                config_items,
                today_key,
            )
            return CorrelationPageData(
                weekly,
                monthly,
                rolling_monthly,
                coverage,
                weights,
                source="live",
            )
        except Exception:
            warning = (
                "Live correlation refresh failed validation. "
                "Showing the verified snapshot instead."
            )
    else:
        warning = (
            "Live correlation database is not configured. "
            "Showing the verified snapshot instead."
        )

    weekly, monthly, rolling_monthly, coverage, weights = load_correlation_outputs()
    return CorrelationPageData(
        weekly,
        monthly,
        rolling_monthly,
        coverage,
        weights,
        source="fallback",
        warning=warning,
    )


def correlation_kpis(
    weekly: pd.DataFrame,
    scope: str,
    metric: str,
    coefficient: str,
) -> Dict[str, Any]:
    """Return same-week and strongest negative lag values for one view."""
    selected = weekly[
        (weekly["scope"] == scope) & (weekly["metric"] == metric)
    ].sort_values("rain_leads_weeks")
    if selected.empty:
        raise ValueError(f"No correlation data for {scope} / {metric}")

    same_week = selected[selected["rain_leads_weeks"] == 0]
    if same_week.empty:
        raise ValueError(f"No same-week correlation for {scope} / {metric}")

    negative = selected[
        pd.to_numeric(selected[coefficient], errors="coerce").lt(0)
    ]
    if negative.empty:
        strongest_lag = None
        strongest_value = None
    else:
        strongest = negative.loc[negative[coefficient].idxmin()]
        strongest_lag = int(strongest["rain_leads_weeks"])
        strongest_value = float(strongest[coefficient])

    row = same_week.iloc[0]
    return {
        "same_week": float(row[coefficient]),
        "strongest_lag": strongest_lag,
        "strongest_value": strongest_value,
        "weeks": int(row["weeks"]),
        "active_weeks": int(row["active_weeks"]),
        "analysis_start": str(row["analysis_start"]),
        "analysis_end": str(row["analysis_end"]),
    }


def correlation_page_summary(
    weekly: pd.DataFrame,
    coverage: pd.DataFrame,
    source: str,
) -> Dict[str, Any]:
    """Return accurate analysis-window and source metadata for the page."""
    return {
        "analysis_start": str(weekly["analysis_start"].min()),
        "analysis_end": str(weekly["analysis_end"].max()),
        "weeks": int(coverage["weeks"].min()),
        "ports": int(coverage["expected_ports"].sum()),
        "regions": int(len(coverage)),
        "status": "Live" if source == "live" else "Verified fallback",
    }


def _style_correlation_chart(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Helvetica Neue, Helvetica, Arial, sans-serif", color="#111827"),
        margin=dict(l=42, r=24, t=62, b=42),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#D9DEE7"),
    )
    fig.update_xaxes(showgrid=False, linecolor="#D9DEE7", zeroline=False)
    fig.update_yaxes(gridcolor="#E9EDF4", linecolor="#D9DEE7", zeroline=True)
    return fig


def build_lag_profile_chart(
    weekly: pd.DataFrame,
    scope: str,
    metric: str,
) -> go.Figure:
    """Compare the three verified coefficients across exact calendar lags."""
    selected = weekly[
        (weekly["scope"] == scope) & (weekly["metric"] == metric)
    ].sort_values("rain_leads_weeks")
    series = [
        ("pearson_anomaly", "De-seasonalized Pearson", CORRELATION_BLUE, "solid"),
        ("pearson_raw", "Raw Pearson", "#64748B", "dot"),
        ("spearman_raw", "Raw Spearman", CORRELATION_TEAL, "dash"),
    ]
    fig = go.Figure()
    for column, label, color, dash in series:
        fig.add_trace(
            go.Scatter(
                x=selected["rain_leads_weeks"],
                y=selected[column],
                mode="lines+markers",
                name=label,
                line=dict(color=color, width=3 if column == "pearson_anomaly" else 1.8, dash=dash),
                marker=dict(size=7),
                hovertemplate="Rain leads %{x}w<br>r = %{y:.3f}<extra>" + label + "</extra>",
            )
        )
    metric_name = "Shipment count" if metric == "shipments" else "Shipment volume"
    fig.update_layout(title=f"Lag profile · {metric_name} · {scope}")
    fig.update_xaxes(title="Rain leads shipments (weeks)", dtick=1)
    fig.update_yaxes(title="Correlation coefficient", range=[-0.6, 0.3], tickformat=".2f")
    fig.add_hline(y=0, line_width=1, line_color="#94A3B8")
    fig = _style_correlation_chart(fig, 480)
    fig.update_layout(
        margin=dict(l=42, r=24, t=130, b=42),
        title=dict(y=0.98, yanchor="top"),
        legend=dict(orientation="h", yanchor="top", y=1.27, x=0),
    )
    return fig


def build_correlation_heatmap(
    weekly: pd.DataFrame,
    metric: str,
    coefficient: str,
    regions: List[str],
) -> go.Figure:
    """Build the signature region-by-lag correlation matrix."""
    regional = weekly[
        weekly["scope"].isin(regions) & (weekly["metric"] == metric)
    ].copy()
    matrix = regional.pivot(
        index="scope", columns="rain_leads_weeks", values=coefficient
    ).reindex(index=regions, columns=range(5))
    text = matrix.map(lambda value: "—" if pd.isna(value) else f"{value:.3f}")
    fig = go.Figure(
        data=go.Heatmap(
            x=[f"{lag}w" for lag in matrix.columns],
            y=list(matrix.index),
            z=matrix.to_numpy(),
            text=text.to_numpy(),
            texttemplate="%{text}",
            textfont=dict(size=13),
            colorscale=[
                [0.0, "#B42318"],
                [0.45, "#F6C7C3"],
                [0.5, "#F8FAFC"],
                [1.0, "#B9D8F2"],
            ],
            zmin=-0.5,
            zmax=0.5,
            colorbar=dict(title="r", thickness=12),
            hovertemplate="%{y}<br>Rain leads %{x}<br>r = %{z:.3f}<extra></extra>",
        )
    )
    metric_name = "Shipment count" if metric == "shipments" else "Shipment volume"
    fig.update_layout(title=f"Regional lag correlation · {metric_name}")
    fig.update_yaxes(autorange="reversed")
    return _style_correlation_chart(fig, 470)


def describe_correlation(value: float) -> str:
    """Return a plain-English strength and direction label."""
    if not math.isfinite(value):
        return "Insufficient data"
    magnitude = abs(value)
    if magnitude < 0.20:
        return "No clear relationship"
    if magnitude < 0.40:
        strength = "Weak"
    elif magnitude < 0.60:
        strength = "Moderate"
    else:
        strength = "Strong"
    direction = "negative" if value < 0 else "positive"
    return f"{strength} {direction} relationship"


def correlation_page_title(metric: str) -> str:
    """Return the exact page title for the selected shipment metric."""
    if metric == "shipments":
        return "Rainfall impact on nickel ore shipments"
    if metric == "volume_mt":
        return "Rainfall impact on nickel ore volume"
    raise ValueError(f"Unsupported correlation metric: {metric}")


def monthly_metric_summary(
    monthly: pd.DataFrame,
    scope: str,
    metric: str,
) -> Dict[str, Any]:
    """Summarize raw and seasonally adjusted monthly correlations."""
    selected = monthly[
        monthly["scope"].eq(scope) & monthly["metric"].eq(metric)
    ]
    if len(selected) != 1:
        raise ValueError(f"Expected one monthly {metric} row for {scope}")
    row = selected.iloc[0]
    raw = float(row["pearson_raw"])
    adjusted = float(row["pearson_anomaly"])
    noun = "shipment count" if metric == "shipments" else "shipment volume"
    if raw <= -0.20 and abs(adjusted) < 0.20:
        explanation = (
            "The overall negative relationship mainly reflects the normal wet season. "
            f"Unusually wet months do not show a clear additional relationship with {noun}."
        )
    elif raw <= -0.20 and adjusted <= -0.20:
        explanation = (
            "The negative relationship remains after normal seasonality is removed, "
            f"so unusually wet months are also associated with lower {noun}."
        )
    else:
        explanation = (
            "The monthly data does not show a clear overall negative relationship "
            f"between rainfall and {noun}."
        )
    return {
        "raw": raw,
        "adjusted": adjusted,
        "verdict": describe_correlation(raw),
        "explanation": explanation,
    }


def build_rolling_monthly_chart(
    rolling_monthly: pd.DataFrame,
    scope: str,
    metric: str,
) -> go.Figure:
    """Plot the selected scope's rolling 24-month raw Pearson correlation."""
    selected = rolling_monthly[
        rolling_monthly["scope"].eq(scope)
        & rolling_monthly["metric"].eq(metric)
    ].copy()
    selected["month"] = pd.to_datetime(selected["month"], errors="coerce")
    selected = selected.dropna(subset=["month", "pearson_raw"]).sort_values("month")
    fig = go.Figure()
    if selected.empty:
        fig.add_annotation(
            text="At least 24 complete months are required.",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(color="#5F6B7A", size=14),
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=selected["month"],
                y=selected["pearson_raw"],
                mode="lines+markers",
                name="24-month correlation",
                line=dict(color=CORRELATION_RED, width=3),
                marker=dict(size=7),
                hovertemplate="Window ending %{x|%b %Y}<br>r = %{y:.3f}<extra></extra>",
            )
        )
    fig.add_hline(y=0, line_width=1.5, line_dash="dash", line_color="#94A3B8")
    fig.update_xaxes(title="24-month window ending")
    fig.update_yaxes(title="Raw Pearson correlation", tickformat=".2f")
    return _style_correlation_chart(fig, 410)


def render_correlation_page() -> None:
    try:
        database_config = dict(st.secrets["database"])
    except Exception:
        database_config = None

    page_data = resolve_correlation_data(database_config)
    weekly = page_data.weekly
    monthly = page_data.monthly
    rolling_monthly = page_data.rolling_monthly
    coverage = page_data.coverage
    if page_data.warning:
        st.warning(page_data.warning)
    summary = correlation_page_summary(
        weekly,
        coverage,
        source=page_data.source,
    )

    st.markdown(
        """
        <style>
        .correlation-hero {border-top:5px solid #002FA7; border-bottom:1px solid #D9DEE7; padding:20px 4px 22px; margin-bottom:18px;}
        .correlation-title {font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; font-size:3rem; line-height:1; font-weight:800; color:#111827; margin:0;}
        .correlation-subtitle {font-family:"Helvetica Neue",Helvetica,Arial,sans-serif; color:#5F6B7A; margin-top:10px; font-size:1rem;}
        .correlation-card {background:#FFFFFF; border:1px solid #D9DEE7; border-radius:4px; padding:20px 22px; min-height:190px;}
        .correlation-label {color:#5F6B7A; font-size:.78rem; text-transform:uppercase; letter-spacing:.02em;}
        .correlation-value {color:#B42318; font-size:3rem; font-weight:780; line-height:1.1; margin-top:10px; font-variant-numeric:tabular-nums;}
        .correlation-verdict {color:#111827; font-size:1.18rem; font-weight:720; margin-top:7px;}
        .correlation-note {color:#5F6B7A; font-size:.88rem; line-height:1.5; margin-top:7px;}
        .correlation-compare {display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:12px 0;}
        .correlation-mini {background:#F5F7FA; border-radius:3px; padding:12px 14px;}
        .correlation-mini-value {color:#334155; font-size:1.55rem; font-weight:740; margin:5px 0 2px; font-variant-numeric:tabular-nums;}
        .correlation-callout {border-left:4px solid #0B5FFF; background:#F5F7FA; padding:12px 16px; color:#334155; margin:8px 0 20px;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    hero = st.empty()
    scopes = ["Philippines weighted"] + REGION_ORDER
    filter_scope, filter_metric = st.columns([1.2, 1])
    with filter_scope:
        scope = st.selectbox("Region", scopes)
    with filter_metric:
        metric_label = st.selectbox(
            "Metric",
            list(CORRELATION_METRICS),
            index=1,
        )
    metric = CORRELATION_METRICS[metric_label]["key"]
    metric_noun = CORRELATION_METRICS[metric_label]["noun"]
    metric_summary = monthly_metric_summary(monthly, scope, metric)
    hero.markdown(
        f"""
        <div class="correlation-hero">
          <div class="correlation-title">{correlation_page_title(metric)}</div>
          <div class="correlation-subtitle">Are wetter months associated with lower {metric_noun}, and is that relationship changing? · {summary["analysis_start"]} to {summary["analysis_end"]} · {summary["status"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    card_one, card_two = st.columns([1, 1])
    with card_one:
        st.markdown(
            f'''<div class="correlation-card">
                <div class="correlation-label">Overall monthly correlation</div>
                <div class="correlation-value">{metric_summary["raw"]:+.3f}</div>
                <div class="correlation-verdict">{metric_summary["verdict"]}</div>
                <div class="correlation-note">Wetter months are compared with total monthly {metric_noun}. Values closer to −1 indicate a stronger negative relationship.</div>
            </div>''',
            unsafe_allow_html=True,
        )
    with card_two:
        st.markdown(
            f'''<div class="correlation-card">
                <div class="correlation-label">What is driving it?</div>
                <div class="correlation-compare">
                    <div class="correlation-mini"><div class="correlation-note">Raw monthly</div><div class="correlation-mini-value">{metric_summary["raw"]:+.3f}</div><div class="correlation-note">Includes the normal wet season</div></div>
                    <div class="correlation-mini"><div class="correlation-note">After seasonality</div><div class="correlation-mini-value">{metric_summary["adjusted"]:+.3f}</div><div class="correlation-note">Compares unusual months</div></div>
                </div>
                <div class="correlation-note">{metric_summary["explanation"]}</div>
            </div>''',
            unsafe_allow_html=True,
        )

    st.markdown("### Rolling 24-month correlation")
    st.caption(
        f"Each point recalculates Raw Pearson using the latest 24 complete months of rainfall and {metric_noun}."
    )
    st.plotly_chart(
        build_rolling_monthly_chart(rolling_monthly, scope, metric),
        use_container_width=True,
    )
    st.markdown(
        '<div class="correlation-callout"><b>How to read the trend:</b> movement from −0.50 toward −0.20 means the negative relationship is weakening. Other factors may be becoming more important, but the trend alone cannot identify or prove those factors.</div>',
        unsafe_allow_html=True,
    )

    st.markdown("### Detailed weekly analysis")
    st.caption(
        f"These charts retain the detailed lag view for {metric_noun}. The summary above remains the primary decision view."
    )
    left, right = st.columns([1.05, 1.35])
    with left:
        st.plotly_chart(
            build_lag_profile_chart(weekly, scope, metric),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            build_correlation_heatmap(
                weekly,
                metric,
                "pearson_anomaly",
                REGION_ORDER,
            ),
            use_container_width=True,
        )

    with st.expander("Method and interpretation"):
        st.markdown(
            f"""
            - The headline compares monthly rainfall with monthly {metric_noun} using Raw Pearson correlation.
            - The seasonally adjusted value compares each month with the normal pattern for the same calendar month.
            - The rolling chart uses the latest 24 complete months at every point.
            - Weekly results use complete Monday–Sunday weeks. Positive lags mean rainfall occurs before the compared shipment week.
            - Regional results are primary because rainfall seasons differ across the Philippines.
            - The national view uses fixed 2021–2025 regional shipment-share weights.

            **Correlation does not establish causation.**
            """
        )


# ============================================================
# Streamlit UI
# ============================================================

def main() -> None:
    today = date.today()
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select page",
        ["Philippine rain", "Rainfall × shipments"],
    )

    if page == "Rainfall × shipments":
        st.sidebar.caption(CORRELATION_SIDEBAR_CAPTION)
        render_correlation_page()
        return

    st.sidebar.divider()
    st.sidebar.subheader("Historical settings")

    year_options = list(range(today.year, 2019, -1))
    selected_years = st.sidebar.multiselect(
        "Historical years",
        options=year_options,
        default=[today.year],
    )
    selected_years = sorted(selected_years)

    selected_regions = st.sidebar.multiselect(
        "Regions",
        options=REGION_ORDER,
        default=REGION_ORDER,
    )

    st.sidebar.caption("Historical charts show one average rainfall point every 7 days.")
    st.sidebar.caption("Historical year options are capped at the current year.")
    st.sidebar.caption("Current-year historical data is capped at today.")
    st.sidebar.caption("Forecast is always today + future 7 days.")
    st.sidebar.caption("Data source: Open-Meteo API. Unit: mm.")

    if page == "Philippine rain":
        st.title("Philippine rain")
        st.caption("Open-Meteo rainfall dashboard for Philippine nickel ore loading regions.")

        if not selected_regions:
            st.warning("Please select at least one region in the sidebar.")
            return

        if not selected_years:
            st.warning("Please select at least one historical year in the sidebar.")
            return

        historical_start_date = date(min(selected_years), 1, 1)
        historical_end_date = min(date(max(selected_years), 12, 31), today)

        # Historical section
        st.header("1. Historical 7-day average rainfall by region")
        st.caption(
            "Each historical bar or line point is the average rainfall inside one non-overlapping 7-day window."
        )

        with st.spinner("Loading historical Open-Meteo rainfall data..."):
            df_hist_daily = load_historical_data_cached(
                start_date=historical_start_date.strftime("%Y-%m-%d"),
                end_date=historical_end_date.strftime("%Y-%m-%d"),
                cache_version=HISTORICAL_CACHE_VERSION,
            )

        failed_hist_ports = df_hist_daily.attrs.get("failed_ports", [])
        if failed_hist_ports:
            with st.expander(f"Historical data warning: {len(failed_hist_ports)} port requests failed"):
                st.write("\n".join(failed_hist_ports))

        df_hist_seven_day = historical_seven_day_region_average(df_hist_daily, selected_years)
        df_hist_seven_day_selected = df_hist_seven_day[
            df_hist_seven_day["region_group"].isin(selected_regions)
        ].copy() if not df_hist_seven_day.empty else pd.DataFrame()

        if not df_hist_seven_day_selected.empty:
            st.dataframe(
                df_hist_seven_day_selected,
                use_container_width=True,
                hide_index=True,
            )

        show_historical_region_charts(df_hist_seven_day_selected, selected_regions, selected_years)

        # Forecast section
        st.header("2. Future 7 days rainfall")
        st.caption(f"Forecast is fixed from today: {today.strftime('%Y-%m-%d')}. It is not affected by historical date selections.")
        st.caption("Forecast uses one batch request first. If batch fails, it automatically falls back to concurrent per-port requests.")

        with st.spinner("Loading today's Open-Meteo 7-day forecast..."):
            df_forecast_daily = load_forecast_data_today_cached(
                today_key=today.strftime("%Y-%m-%d"),
                forecast_days=7,
                cache_version=FORECAST_CACHE_VERSION,
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
