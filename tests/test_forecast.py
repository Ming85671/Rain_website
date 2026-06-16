import unittest
from unittest.mock import patch

import pandas as pd

import rain


class ForecastBatchTests(unittest.TestCase):
    def test_load_forecast_uses_one_batch_request_and_maps_each_port(self):
        test_ports = {
            "Port A": {"lat": 1.0, "lon": 101.0, "region_group": "Region A"},
            "Port B": {"lat": 2.0, "lon": 102.0, "region_group": "Region B"},
        }
        api_response = [
            {"daily": {"time": ["2026-06-11"], "precipitation_sum": [1.5]}},
            {"daily": {"time": ["2026-06-11"], "precipitation_sum": [2.5]}},
        ]

        rain.load_forecast_data_today_cached.clear()
        with (
            patch.object(rain, "PORTS", test_ports),
            patch.object(rain, "request_json", return_value=api_response) as request_json,
        ):
            result = rain.load_forecast_data_today_cached("2026-06-11", forecast_days=7)

        self.assertEqual(request_json.call_count, 1)
        _, params = request_json.call_args.args
        self.assertEqual(params["latitude"], "1.0,2.0")
        self.assertEqual(params["longitude"], "101.0,102.0")
        self.assertEqual(set(result["port_name"]), {"Port A", "Port B"})
        self.assertEqual(result.attrs["failed_ports"], [])

    def test_batch_request_uses_dns_fallback_when_open_meteo_hostname_fails(self):
        ports = {
            "Port A": {"lat": 1.0, "lon": 101.0, "region_group": "Region A"},
        }
        api_response = {
            "daily": {"time": ["2026-06-11"], "precipitation_sum": [1.5]}
        }
        fallback_response = unittest.mock.Mock()
        fallback_response.json.return_value = api_response

        with (
            patch.object(
                rain,
                "request_json",
                side_effect=RuntimeError("NameResolutionError: api.open-meteo.com"),
            ),
            patch.object(rain, "resolve_hostname_doh", return_value="188.40.99.226"),
            patch.object(rain.requests, "get", return_value=fallback_response) as requests_get,
        ):
            result = rain.fetch_openmeteo_forecast_daily_batch(ports)

        self.assertEqual(result, [api_response])
        self.assertEqual(requests_get.call_args.args[0], "https://188.40.99.226/v1/forecast")
        self.assertEqual(requests_get.call_args.kwargs["headers"]["Host"], "api.open-meteo.com")


class HistoricalSevenDayAverageTests(unittest.TestCase):
    def test_historical_seven_day_region_average_uses_non_overlapping_windows(self):
        rows = []
        for day, precipitation in enumerate(range(1, 16), start=1):
            rows.append(
                {
                    "source": "OpenMeteo",
                    "data_type": "historical",
                    "region_group": "Region A",
                    "port_name": "Port A",
                    "latitude": 1.0,
                    "longitude": 101.0,
                    "date": f"2026-01-{day:02d}",
                    "precipitation_mm": precipitation,
                }
            )

        result = rain.historical_seven_day_region_average(pd.DataFrame(rows))

        self.assertEqual(len(result), 3)
        self.assertEqual(result["year"].tolist(), [2026, 2026, 2026])
        self.assertEqual(result["window_label"].tolist(), ["Jan 1-7", "Jan 8-14", "Jan 15-15"])
        self.assertEqual(result["window_sort"].tolist(), [1, 8, 15])
        self.assertEqual(result["average_precipitation_mm"].tolist(), [4.0, 11.0, 15.0])

    def test_historical_seven_day_region_average_averages_ports_inside_window(self):
        rows = [
            {
                "source": "OpenMeteo",
                "data_type": "historical",
                "region_group": "Region A",
                "port_name": port_name,
                "latitude": 1.0,
                "longitude": 101.0,
                "date": "2026-01-01",
                "precipitation_mm": precipitation,
            }
            for port_name, precipitation in [("Port A", 2.0), ("Port B", 6.0)]
        ]

        result = rain.historical_seven_day_region_average(pd.DataFrame(rows))

        self.assertEqual(result.loc[0, "port_count"], 2)
        self.assertEqual(result.loc[0, "observation_days"], 1)
        self.assertEqual(result.loc[0, "average_precipitation_mm"], 4.0)

    def test_historical_seven_day_region_average_groups_december_31_with_prior_week(self):
        rows = []
        for day in range(24, 32):
            rows.append(
                {
                    "source": "OpenMeteo",
                    "data_type": "historical",
                    "region_group": "Region A",
                    "port_name": "Port A",
                    "latitude": 1.0,
                    "longitude": 101.0,
                    "date": f"2026-12-{day:02d}",
                    "precipitation_mm": float(day),
                }
            )

        result = rain.historical_seven_day_region_average(pd.DataFrame(rows))

        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "window_label"], "Dec 24-31")
        self.assertEqual(result.loc[0, "observation_days"], 8)
        self.assertEqual(result.loc[0, "average_precipitation_mm"], 27.5)


class HistoricalChartStyleTests(unittest.TestCase):
    def test_rainfall_axis_max_rounds_above_highest_value(self):
        self.assertEqual(rain.rainfall_axis_max([30.99]), 35)
        self.assertEqual(rain.rainfall_axis_max([35.0]), 40)
        self.assertEqual(rain.rainfall_axis_max([]), 5)

    def test_year_color_map_keeps_2026_stable_when_more_years_are_selected(self):
        first_map = rain.year_color_map([2024, 2025, 2026])
        second_map = rain.year_color_map([2026, 2027])

        self.assertEqual(first_map["2026"], "#0B5FFF")
        self.assertEqual(second_map["2026"], "#0B5FFF")


if __name__ == "__main__":
    unittest.main()
