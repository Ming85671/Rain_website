import unittest
from unittest.mock import patch

import pandas as pd
import plotly.graph_objects as go

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


class ForecastRegionAverageTests(unittest.TestCase):
    def test_weekly_outlook_prefers_observed_past_days_and_requires_complete_ports(self):
        today = pd.Timestamp("2026-09-30").date()
        dates = pd.date_range("2026-09-28", "2026-10-11")
        forecast = pd.DataFrame([
            {"region_group": "Palawan", "port_name": port, "date": day,
             "precipitation_mm": 100.0 if port == "Incomplete" else 10.0}
            for port in ("Complete", "Incomplete") for day in dates
            if not (port == "Incomplete" and day == pd.Timestamp("2026-10-04"))
        ])
        historical = pd.DataFrame([
            {"region_group": "Palawan", "port_name": "Complete", "date": day,
             "precipitation_mm": 3.0}
            for day in pd.date_range("2026-09-28", "2026-09-30")
        ])

        result = rain.weekly_rainfall_outlook(historical, forecast, today)
        palawan = result[result["region_group"] == "Palawan"].reset_index(drop=True)
        overall = result[result["region_group"] == "Philippines overall"].reset_index(drop=True)

        self.assertEqual(palawan["hover_label"].tolist(), [
            "2026-09-28 to 2026-10-04", "2026-10-05 to 2026-10-11"
        ])
        self.assertEqual(palawan["port_count"].tolist(), [1, 2])
        self.assertEqual(palawan["historical_port_days"].tolist(), [2, 0])
        self.assertEqual(palawan["forecast_port_days"].tolist(), [5, 14])
        self.assertEqual(palawan["average_precipitation_mm"].tolist(), [8.0, 55.0])
        self.assertEqual(overall["average_precipitation_mm"].tolist(), [8.0, 55.0])

    def test_forecast_daily_region_total_includes_per_port_daily_average(self):
        df_daily = pd.DataFrame(
            [
                {
                    "region_group": "Palawan",
                    "date": pd.Timestamp("2026-06-20"),
                    "port_name": "Port A",
                    "precipitation_mm": 20.0,
                },
                {
                    "region_group": "Palawan",
                    "date": pd.Timestamp("2026-06-20"),
                    "port_name": "Port B",
                    "precipitation_mm": 40.0,
                },
            ]
        )

        result = rain.forecast_daily_region_total(df_daily)

        self.assertEqual(result.loc[0, "regional_total_precipitation_mm"], 60.0)
        self.assertEqual(result.loc[0, "port_count"], 2)
        self.assertEqual(result.loc[0, "daily_region_average_precipitation_mm"], 30.0)

    def test_forecast_average_by_region_averages_across_ports_and_days(self):
        region_daily = pd.DataFrame(
            [
                {
                    "region_group": "Palawan",
                    "date": pd.Timestamp("2026-06-20"),
                    "port_count": 4,
                    "regional_total_precipitation_mm": 120.0,
                },
                {
                    "region_group": "Palawan",
                    "date": pd.Timestamp("2026-06-21"),
                    "port_count": 4,
                    "regional_total_precipitation_mm": 80.0,
                },
            ]
        )

        result = rain.forecast_average_by_region(region_daily)

        self.assertEqual(result.loc[0, "forecast_days"], 2)
        self.assertEqual(result.loc[0, "average_7d_precipitation_mm"], 25.0)

    def test_forecast_axis_scales_with_small_and_large_values(self):
        self.assertEqual(rain.forecast_rainfall_axis([22.4]), (30, 5))
        self.assertEqual(rain.forecast_rainfall_axis([48.0]), (60, 10))
        self.assertEqual(rain.forecast_rainfall_axis([92.0]), (120, 20))
        self.assertEqual(rain.forecast_rainfall_axis([692.9]), (800, 100))
        self.assertEqual(rain.forecast_rainfall_axis([]), (5, 5))

    def test_forecast_summary_axes_use_dynamic_horizontal_grid_interval(self):
        fig = go.Figure()

        rain.apply_forecast_summary_axes(fig, 30, 5)

        self.assertEqual(tuple(fig.layout.yaxis.range), (0, 30))
        self.assertEqual(fig.layout.yaxis.dtick, 5)
        self.assertTrue(fig.layout.yaxis.showgrid)
        self.assertEqual(fig.layout.yaxis.gridcolor, "#E5E7EB")
        self.assertEqual({shape.y0 for shape in fig.layout.shapes}, {0, 30})

    def test_forecast_chart_axes_can_expand_to_container_width(self):
        fig = go.Figure()

        rain.apply_forecast_rainfall_axes(fig, 30, 5, height=430, width=None)

        self.assertEqual(fig.layout.height, 430)
        self.assertIsNone(fig.layout.width)
        self.assertEqual({shape.y0 for shape in fig.layout.shapes}, {0, 30})


class HistoricalSevenDayAverageTests(unittest.TestCase):
    def _regional_rows(self, result):
        return result[result["region_group"] != "Philippines overall"].reset_index(drop=True)

    def test_monday_sunday_weeks_do_not_split_at_month_or_year_boundary(self):
        dates = list(pd.date_range("2025-12-29", "2026-01-04")) + list(
            pd.date_range("2026-09-21", "2026-10-04")
        )
        rows = pd.DataFrame([
            {"region_group": "Palawan", "port_name": "Port A", "date": day,
             "precipitation_mm": 7.0}
            for day in dates
        ])

        result = self._regional_rows(
            rain.historical_seven_day_region_average(rows, selected_years=[2026])
        )

        self.assertEqual(result["hover_label"].tolist(), [
            "2025-12-29 to 2026-01-04",
            "2026-09-21 to 2026-09-27",
            "2026-09-28 to 2026-10-04",
        ])
        self.assertEqual(result["window_label"].tolist(), [
            "Dec 29-Jan 4", "Sep 21-27", "Sep 28-Oct 4"
        ])
        self.assertEqual(result["observation_days"].tolist(), [7, 7, 7])
        self.assertEqual(result["average_precipitation_mm"].tolist(), [7.0, 7.0, 7.0])

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
        regional_result = self._regional_rows(result)

        self.assertEqual(len(regional_result), 3)
        self.assertEqual(regional_result["year"].tolist(), [2026, 2026, 2026])
        self.assertEqual(regional_result["window_label"].tolist(), ["Dec 29-Jan 4", "Jan 5-11", "Jan 12-18"])
        self.assertEqual(regional_result["window_sort"].tolist(), [-2, 5, 12])
        self.assertEqual(regional_result["average_precipitation_mm"].tolist(), [2.5, 8.0, 13.5])

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
        regional_result = self._regional_rows(result)

        self.assertEqual(regional_result.loc[0, "port_count"], 2)
        self.assertEqual(regional_result.loc[0, "observation_days"], 1)
        self.assertEqual(regional_result.loc[0, "average_precipitation_mm"], 4.0)

    def test_historical_seven_day_region_average_adds_philippines_overall(self):
        rows = [
            {
                "source": "OpenMeteo",
                "data_type": "historical",
                "region_group": region,
                "port_name": port_name,
                "latitude": 1.0,
                "longitude": 101.0,
                "date": "2026-01-01",
                "precipitation_mm": precipitation,
            }
            for region, port_name, precipitation in [
                ("Surigao-Dinagat-Caraga", "Port A", 2.0),
                ("Palawan", "Port B", 6.0),
                ("Palawan", "Port C", 10.0),
            ]
        ]

        result = rain.historical_seven_day_region_average(pd.DataFrame(rows))
        overall = result[result["region_group"] == "Philippines overall"].reset_index(drop=True)

        self.assertEqual(len(overall), 1)
        self.assertEqual(overall.loc[0, "window_label"], "Dec 29-Jan 4")
        self.assertEqual(overall.loc[0, "port_count"], 3)
        self.assertEqual(overall.loc[0, "observation_days"], 1)
        self.assertEqual(overall.loc[0, "average_precipitation_mm"], 6.0)

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
        regional_result = self._regional_rows(result)

        self.assertEqual(len(regional_result), 2)
        self.assertEqual(regional_result["window_label"].tolist(), ["Dec 21-27", "Dec 28-Jan 3"])
        self.assertEqual(regional_result["observation_days"].tolist(), [4, 4])
        self.assertEqual(regional_result["average_precipitation_mm"].tolist(), [25.5, 29.5])


class HistoricalChartStyleTests(unittest.TestCase):
    def test_weekly_charts_show_forecast_line_and_bar_separately(self):
        historical = pd.DataFrame([{
            "region_group": "Palawan", "year": 2026, "year_label": "2026",
            "window_start": pd.Timestamp("2026-09-21"), "window_sort": 264,
            "average_precipitation_mm": 4.0,
            "hover_label": "2026-09-21 to 2026-09-27",
            "port_count": 1, "observation_days": 7,
        }])
        outlook = pd.DataFrame([
            {"region_group": "Palawan", "window_sort": 271,
             "average_precipitation_mm": 8.0,
             "hover_label": "2026-09-28 to 2026-10-04",
             "historical_port_days": 2, "forecast_port_days": 5, "port_count": 1},
            {"region_group": "Palawan", "window_sort": 278,
             "average_precipitation_mm": 12.0,
             "hover_label": "2026-10-05 to 2026-10-11",
             "historical_port_days": 0, "forecast_port_days": 7, "port_count": 1},
        ])
        with (
            patch.object(rain.st, "subheader"),
            patch.object(rain.st, "plotly_chart") as plotly_chart,
        ):
            rain.show_historical_region_charts(historical, ["Palawan"], [2026], outlook)

        line, bar = [call.args[0] for call in plotly_chart.call_args_list]
        forecast_line = line.data[-1]
        forecast_bar = bar.data[-1]
        self.assertEqual(forecast_line.line.dash, "dash")
        self.assertEqual(list(forecast_line.x), [264, 271, 278])
        self.assertEqual(forecast_bar.marker.color, rain.OUTLOOK_COLOR)
        self.assertEqual(list(forecast_bar.x), [271, 278])
        self.assertTrue(bar.data[0].showlegend)

    def test_rainfall_axis_max_rounds_above_highest_value(self):
        self.assertEqual(rain.rainfall_axis_max([30.99]), 35)
        self.assertEqual(rain.rainfall_axis_max([35.0]), 40)
        self.assertEqual(rain.rainfall_axis_max([]), 5)

    def test_year_color_map_keeps_2026_stable_when_more_years_are_selected(self):
        first_map = rain.year_color_map([2024, 2025, 2026])
        second_map = rain.year_color_map([2026, 2027])

        self.assertEqual(first_map["2026"], "#0B5FFF")
        self.assertEqual(second_map["2026"], "#0B5FFF")

    def test_year_color_map_reserves_2026_color_from_other_years(self):
        color_map = rain.year_color_map([2024, 2025, 2026, 2027])

        for year_label, color in color_map.items():
            if year_label != "2026":
                self.assertNotEqual(color, "#0B5FFF")

    def test_historical_axes_draw_bottom_and_top_horizontal_lines(self):
        fig = go.Figure()

        rain.apply_historical_rainfall_axes(fig, 35)

        self.assertEqual(len(fig.layout.shapes), 2)
        lines_by_y = {line.y0: line for line in fig.layout.shapes}
        bottom_line = lines_by_y[0]
        top_line = lines_by_y[35]
        self.assertEqual(bottom_line.type, "line")
        self.assertEqual(bottom_line.y1, 0)
        self.assertEqual(bottom_line.xref, "paper")
        self.assertEqual(bottom_line.yref, "y")
        self.assertEqual(top_line.type, "line")
        self.assertEqual(top_line.y1, 35)
        self.assertEqual(top_line.xref, "paper")
        self.assertEqual(top_line.yref, "y")

    def test_year_trace_styles_keep_2026_dominant_and_quiet_other_years(self):
        fig = go.Figure()
        fig.add_scatter(name="2025", x=[1, 8], y=[4.0, 7.0])
        fig.add_scatter(name="2026", x=[1, 8], y=[5.0, 8.0])

        rain.apply_year_trace_styles(fig)

        trace_by_name = {trace.name: trace for trace in fig.data}
        self.assertEqual(trace_by_name["2026"].line.width, 3.5)
        self.assertEqual(trace_by_name["2026"].opacity, 1.0)
        self.assertEqual(trace_by_name["2025"].line.width, 1.8)
        self.assertEqual(trace_by_name["2025"].opacity, 0.6)


if __name__ == "__main__":
    unittest.main()
