import builtins
import importlib.util
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

import correlation_analysis as ca


class PortMappingTests(unittest.TestCase):
    def test_port_alias_maps_hinituan_to_canonical_port(self):
        self.assertEqual(
            ca.PORT_ALIASES["Hinituan & Talavera Islands"],
            "Hinituan&Talavera Islands",
        )
        shipments = pd.DataFrame(
            {
                "load_port": ["Hinituan & Talavera Islands"],
                "cargo": ["Nickel ore"],
            }
        )

        result = ca.map_shipment_regions(
            shipments,
            {"Hinituan&Talavera Islands": "Surigao"},
        )

        self.assertNotIn("port_key", shipments.columns)
        self.assertNotIn("region_group", shipments.columns)
        self.assertEqual(result.loc[0, "port_key"], "Hinituan&Talavera Islands")
        self.assertEqual(result.loc[0, "region_group"], "Surigao")
        self.assertEqual(result.loc[0, "cargo"], "Nickel ore")

    def test_unmapped_error_lists_every_original_load_port(self):
        shipments = pd.DataFrame(
            {"load_port": ["Unknown Z", "Known", "Unknown A", "Unknown Z"]}
        )

        with self.assertRaises(ValueError) as raised:
            ca.map_shipment_regions(shipments, {"Known": "Region A"})

        message = str(raised.exception)
        self.assertIn("Unknown A", message)
        self.assertIn("Unknown Z", message)
        self.assertNotIn("Known", message)

    def test_unmapped_error_formats_null_and_mixed_type_ports(self):
        shipments = pd.DataFrame({"load_port": [None, "Zulu", 17]})

        with self.assertRaises(ValueError) as raised:
            ca.map_shipment_regions(shipments, {})

        self.assertEqual(
            str(raised.exception),
            "Unmapped shipment ports: 17, <missing>, Zulu",
        )


class WeeklyPanelTests(unittest.TestCase):
    def test_monday_start_normalizes_date_like_values(self):
        values = pd.Series(
            ["2025-01-06 14:30", "2025-01-12", "not-a-date"],
            index=["first", "second", "invalid"],
        )

        result = ca.monday_start(values)

        expected = pd.Series(
            pd.to_datetime(["2025-01-06", "2025-01-06", None]),
            index=values.index,
        )
        assert_series_equal(result, expected)

    def test_monday_start_accepts_lists(self):
        result = ca.monday_start(["2025-01-07", "2025-01-13"])

        self.assertEqual(
            result.tolist(),
            list(pd.to_datetime(["2025-01-06", "2025-01-13"])),
        )

    def test_monday_start_accepts_datetime_index(self):
        result = ca.monday_start(
            pd.DatetimeIndex(["2025-01-08 12:00", "2025-01-19"])
        )

        self.assertEqual(
            result.tolist(),
            list(pd.to_datetime(["2025-01-06", "2025-01-13"])),
        )

    def test_weekly_panel_excludes_out_of_range_valid_rows(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": [
                    "2025-01-07",
                    "2025-01-08 06:30",
                    "2024-12-30",
                ],
                "region_group": ["Region A"] * 3,
                "vsl_name": ["One", "Two", "Earlier"],
                "voy_intake_mt": ["10", "20", "999"],
            }
        )
        weeks = pd.DatetimeIndex(["2025-01-06", "2025-01-13"])

        result = ca.build_shipment_weekly_panel(shipments, ["Region A"], weeks)

        self.assertEqual(result["shipments"].tolist(), [2, 0])
        self.assertEqual(result["volume_mt"].tolist(), [30.0, 0.0])

    def test_weekly_panel_rejects_invalid_and_missing_dates_with_row_indices(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": ["2025-01-07", "bad-date", None],
                "region_group": ["Region A"] * 3,
                "vsl_name": ["One", "Two", "Three"],
                "voy_intake_mt": [10, 20, 30],
            },
            index=[3, 8, 13],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_shipment_weekly_panel(
                shipments,
                ["Region A"],
                pd.DatetimeIndex(["2025-01-06"]),
            )

        self.assertEqual(
            str(raised.exception),
            "Invalid or missing load_start_date at shipment rows: 8, 13",
        )

    def test_weekly_panel_rejects_missing_and_blank_vessel_names_with_row_indices(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": ["2025-01-07", "2025-01-08", "2025-01-09"],
                "region_group": ["Region A"] * 3,
                "vsl_name": ["One", None, "  \t"],
                "voy_intake_mt": [10, 20, 30],
            },
            index=[3, 8, 13],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_shipment_weekly_panel(
                shipments,
                ["Region A"],
                pd.DatetimeIndex(["2025-01-06"]),
            )

        self.assertEqual(
            str(raised.exception),
            "Missing or blank vsl_name at shipment rows: 8, 13",
        )

    def test_weekly_panel_rejects_missing_regions_with_row_indices(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": ["2025-01-07", "2025-01-08", "2025-01-09"],
                "region_group": ["Region A", None, float("nan")],
                "vsl_name": ["One", "Two", "Three"],
                "voy_intake_mt": [10, 20, 30],
            },
            index=[3, 8, 13],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_shipment_weekly_panel(
                shipments,
                ["Region A"],
                pd.DatetimeIndex(["2025-01-06"]),
            )

        self.assertEqual(
            str(raised.exception),
            "Missing region_group at shipment rows: 8, 13",
        )

    def test_weekly_panel_rejects_invalid_and_missing_volume_with_row_indices(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": ["2025-01-07", "2025-01-08", "2025-01-09"],
                "region_group": ["Region A"] * 3,
                "vsl_name": ["One", "Two", "Three"],
                "voy_intake_mt": [10, "invalid", None],
            },
            index=[3, 8, 13],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_shipment_weekly_panel(
                shipments,
                ["Region A"],
                pd.DatetimeIndex(["2025-01-06"]),
            )

        self.assertEqual(
            str(raised.exception),
            "Invalid or missing voy_intake_mt at shipment rows: 8, 13",
        )

    def test_weekly_panel_rejects_infinite_volume_with_row_indices(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": ["2025-01-07", "2025-01-08"],
                "region_group": ["Region A", "Region A"],
                "vsl_name": ["One", "Two"],
                "voy_intake_mt": [float("inf"), float("-inf")],
            },
            index=[5, 12],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_shipment_weekly_panel(
                shipments,
                ["Region A"],
                pd.DatetimeIndex(["2025-01-06"]),
            )

        self.assertEqual(
            str(raised.exception),
            "Invalid or missing voy_intake_mt at shipment rows: 5, 12",
        )

    def test_weekly_panel_rejects_negative_volume_with_row_indices(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": ["2025-01-07", "2025-01-08", "2025-01-09"],
                "region_group": ["Region A"] * 3,
                "vsl_name": ["One", "Two", "Three"],
                "voy_intake_mt": [10, -1, -20],
            },
            index=[3, 8, 13],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_shipment_weekly_panel(
                shipments,
                ["Region A"],
                pd.DatetimeIndex(["2025-01-06"]),
            )

        self.assertEqual(
            str(raised.exception),
            "Negative voy_intake_mt at shipment rows: 8, 13",
        )

    def test_weekly_panel_rejects_duplicate_regions(self):
        with self.assertRaisesRegex(ValueError, "Duplicate regions: Region A"):
            ca.build_shipment_weekly_panel(
                pd.DataFrame(),
                ["Region A", "Region A"],
                pd.DatetimeIndex(["2025-01-06"]),
            )

    def test_weekly_panel_rejects_non_monday_week(self):
        with self.assertRaisesRegex(ValueError, "Mondays"):
            ca.build_shipment_weekly_panel(
                pd.DataFrame(),
                ["Region A"],
                pd.DatetimeIndex(["2025-01-07"]),
            )

    def test_weekly_panel_rejects_duplicate_normalized_weeks(self):
        with self.assertRaisesRegex(ValueError, "Duplicate weeks"):
            ca.build_shipment_weekly_panel(
                pd.DataFrame(),
                ["Region A"],
                ["2025-01-06", "2025-01-06 12:00"],
            )

    def test_weekly_panel_rejects_timezone_aware_weeks(self):
        with self.assertRaisesRegex(ValueError, "timezone-naive"):
            ca.build_shipment_weekly_panel(
                pd.DataFrame(),
                ["Region A"],
                pd.DatetimeIndex(["2025-01-06"], tz="Asia/Shanghai"),
            )

    def test_weekly_panel_normalizes_monday_times(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": ["2025-01-07"],
                "region_group": ["Region A"],
                "vsl_name": ["One"],
                "voy_intake_mt": [25.0],
            }
        )

        result = ca.build_shipment_weekly_panel(
            shipments,
            ["Region A"],
            ["2025-01-06 12:00"],
        )

        self.assertEqual(result.loc[0, "week_start"], pd.Timestamp("2025-01-06"))

    def test_weekly_panel_returns_all_region_week_pairs_with_zeros(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": ["2025-01-07"],
                "region_group": ["Region A"],
                "vsl_name": ["One"],
                "voy_intake_mt": [25.0],
            }
        )
        weeks = pd.date_range("2025-01-06", periods=2, freq="W-MON")

        result = ca.build_shipment_weekly_panel(
            shipments,
            ["Region A", "Region B"],
            weeks,
        )

        expected = pd.DataFrame(
            {
                "region_group": ["Region A", "Region A", "Region B", "Region B"],
                "week_start": list(weeks) * 2,
                "shipments": [1, 0, 0, 0],
                "volume_mt": [25.0, 0.0, 0.0, 0.0],
            }
        )
        assert_frame_equal(result, expected, check_dtype=False)


class RainfallPanelTests(unittest.TestCase):
    def test_build_rain_weekly_panel_averages_ports_then_days(self):
        rain = pd.DataFrame(
            {
                "region_group": ["A"] * 5,
                "port_name": ["P1", "P1", "P2", "P1", "P2"],
                "date": [
                    "2025-01-06 01:00",
                    "2025-01-06 12:00",
                    "2025-01-06",
                    "2025-01-07",
                    "2025-01-07",
                ],
                "precipitation_mm": [2.0, 4.0, 7.0, 4.0, 8.0],
            }
        )

        result = ca.build_rain_weekly_panel(rain, ["2025-01-06"])

        expected = pd.DataFrame(
            {
                "region_group": ["A"],
                "week_start": pd.to_datetime(["2025-01-06"]),
                "rain_mm_day": [5.5],
                "rain_days": [2],
                "min_ports": [2],
            }
        )
        assert_frame_equal(result, expected, check_dtype=False)

    def test_build_rain_weekly_panel_rejects_bad_precipitation_with_row_indices(self):
        rain = pd.DataFrame(
            {
                "region_group": ["A", "A", "A", "A", "A"],
                "port_name": ["P1", "P2", "P3", "P4", "P5"],
                "date": [
                    "2025-01-06",
                    "bad-date",
                    "2025-01-07",
                    "2025-01-08",
                    "2025-01-09",
                ],
                "precipitation_mm": [
                    1.0,
                    "trace",
                    None,
                    float("inf"),
                    float("-inf"),
                ],
            },
            index=[4, 9, 15, 22, 27],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_rain_weekly_panel(rain, ["2025-01-06"])

        self.assertEqual(
            str(raised.exception),
            "Invalid or missing precipitation_mm at rainfall rows: 9, 15, 22, 27",
        )

    def test_build_rain_weekly_panel_rejects_bad_and_missing_dates_with_row_indices(self):
        rain = pd.DataFrame(
            {
                "region_group": ["A", "A", "A"],
                "port_name": ["P1", "P1", "P1"],
                "date": ["not-a-date", None, "2025-01-07"],
                "precipitation_mm": [100.0, 2.0, 3.0],
            },
            index=[2, 7, 11],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_rain_weekly_panel(rain, ["2025-01-06"])

        self.assertEqual(
            str(raised.exception),
            "Invalid or missing date at rainfall rows: 2, 7",
        )

    def test_build_rain_weekly_panel_rejects_missing_regions_with_row_indices(self):
        rain = pd.DataFrame(
            {
                "region_group": [None, "A"],
                "port_name": ["P1", "P2"],
                "date": ["2025-01-06", "2025-01-07"],
                "precipitation_mm": [1.0, 2.0],
            },
            index=[4, 9],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_rain_weekly_panel(rain, ["2025-01-06"])

        self.assertEqual(
            str(raised.exception),
            "Missing region_group at rainfall rows: 4",
        )

    def test_build_rain_weekly_panel_rejects_missing_ports_with_row_indices(self):
        rain = pd.DataFrame(
            {
                "region_group": ["A", "A"],
                "port_name": [None, "P2"],
                "date": ["2025-01-06", "2025-01-07"],
                "precipitation_mm": [1.0, 2.0],
            },
            index=[6, 10],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_rain_weekly_panel(rain, ["2025-01-06"])

        self.assertEqual(
            str(raised.exception),
            "Missing port_name at rainfall rows: 6",
        )

    def test_build_rain_weekly_panel_rejects_negative_precipitation_with_row_indices(self):
        rain = pd.DataFrame(
            {
                "region_group": ["A", "A", "A"],
                "port_name": ["P1", "P2", "P3"],
                "date": ["2025-01-06", "2025-01-07", "2025-01-08"],
                "precipitation_mm": [1.0, -0.1, -5.0],
            },
            index=[3, 8, 14],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_rain_weekly_panel(rain, ["2025-01-06"])

        self.assertEqual(
            str(raised.exception),
            "Negative precipitation_mm at rainfall rows: 8, 14",
        )

    def test_add_weekly_anomalies_centers_each_metric_by_region_and_iso_week(self):
        panel = pd.DataFrame(
            {
                "region_group": ["A", "A", "B", "B"],
                "week_start": pd.to_datetime(
                    ["2024-01-01", "2024-12-30", "2024-01-01", "2024-12-30"]
                ),
                "rain_mm_day": [2.0, 6.0, 10.0, 14.0],
                "shipments": [1.0, 5.0, 20.0, 22.0],
                "volume_mt": [10.0, 40.0, 100.0, 300.0],
            }
        )

        result = ca.add_weekly_anomalies(panel)

        self.assertEqual(result["iso_week"].tolist(), [1, 1, 1, 1])
        self.assertEqual(
            result["rain_mm_day_anomaly"].tolist(), [-2.0, 2.0, -2.0, 2.0]
        )
        self.assertEqual(
            result["shipments_anomaly"].tolist(), [-2.0, 2.0, -1.0, 1.0]
        )
        self.assertEqual(
            result["volume_mt_anomaly"].tolist(), [-15.0, 15.0, -100.0, 100.0]
        )


class CorrelationTests(unittest.TestCase):
    @staticmethod
    def _lag_panel(week_starts, scopes=None, index=None):
        size = len(week_starts)
        return pd.DataFrame(
            {
                "region_group": scopes or ["A"] * size,
                "week_start": week_starts,
                "rain_mm_day": list(range(1, size + 1)),
                "rain_mm_day_anomaly": list(range(1, size + 1)),
                "shipments": list(range(1, size + 1)),
                "shipments_anomaly": list(range(1, size + 1)),
                "volume_mt": list(range(10, 10 * size + 1, 10)),
                "volume_mt_anomaly": list(range(10, 10 * size + 1, 10)),
            },
            index=index,
        )

    def test_correlation_drops_missing_pairs_before_pearson(self):
        result = ca.correlation([1.0, 2.0, None, 4.0], [2.0, 4.0, 100.0, 8.0])

        self.assertAlmostEqual(result, 1.0)

    def test_correlation_and_pair_count_exclude_non_finite_pairs(self):
        left = [1.0, 2.0, float("inf"), 4.0, 5.0]
        right = [2.0, 4.0, 6.0, 8.0, float("-inf")]

        self.assertAlmostEqual(ca.correlation(left, right), 1.0)
        self.assertEqual(ca._pair_count(left, right), 3)

    def test_correlation_pairs_series_by_position_not_index_label(self):
        left = pd.Series([1.0, 2.0, 3.0], index=[10, 11, 12])
        right = pd.Series([2.0, 4.0, 6.0], index=[20, 21, 22])

        self.assertAlmostEqual(ca.correlation(left, right), 1.0)

    def test_correlation_returns_nan_for_short_or_constant_pairs(self):
        self.assertTrue(math.isnan(ca.correlation([1, 2], [2, 4])))
        self.assertTrue(math.isnan(ca.correlation([1, 1, 1], [1, 2, 3])))
        self.assertTrue(math.isnan(ca.correlation([1, 2, 3], [7, 7, 7])))

    def test_spearman_ranks_average_ties(self):
        result = ca.correlation([1, 2, 2, 4], [10, 20, 30, 40], rank=True)

        self.assertAlmostEqual(result, 0.9486832980505138)

    def test_lag_correlations_use_future_metrics_and_keep_metrics_separate(self):
        panel = pd.DataFrame(
            {
                "region_group": ["A"] * 6,
                "week_start": pd.date_range("2025-01-06", periods=6, freq="W-MON"),
                "rain_mm_day": [1, 2, 3, 4, 5, 6],
                "rain_mm_day_anomaly": [1, 2, 3, 4, 5, 6],
                "shipments": [9, 8, 6, None, 4, 3],
                "shipments_anomaly": [9, 8, 6, None, 4, 3],
                "volume_mt": [90, 80, 10, 20, 30, 40],
                "volume_mt_anomaly": [90, 80, 10, 20, 30, 40],
            }
        )

        result = ca.calculate_lag_correlations(panel, max_lag=2)

        self.assertEqual(set(result["metric"]), {"shipments", "volume_mt"})
        lag_two = result[result["rain_leads_weeks"] == 2].set_index("metric")
        self.assertAlmostEqual(lag_two.loc["shipments", "pearson_raw"], -1.0)
        self.assertAlmostEqual(lag_two.loc["shipments", "spearman_raw"], -1.0)
        self.assertAlmostEqual(lag_two.loc["shipments", "pearson_anomaly"], -1.0)
        self.assertAlmostEqual(lag_two.loc["volume_mt", "pearson_raw"], 1.0)
        self.assertEqual(lag_two.loc["shipments", "weeks"], 3)
        self.assertEqual(lag_two.loc["volume_mt", "weeks"], 4)
        self.assertEqual(lag_two.loc["shipments", "active_weeks"], 5)
        self.assertEqual(lag_two.loc["volume_mt", "active_weeks"], 6)
        self.assertEqual(lag_two.loc["shipments", "scope"], "A")
        self.assertEqual(
            list(result.columns),
            [
                "scope", "metric", "rain_leads_weeks", "pearson_raw",
                "spearman_raw", "pearson_anomaly", "weeks", "active_weeks",
                "analysis_start", "analysis_end",
            ],
        )
        self.assertEqual(set(result["analysis_start"]), {"2025-01-06"})
        self.assertEqual(set(result["analysis_end"]), {"2025-02-10"})

    def test_lag_correlations_require_exact_future_calendar_week(self):
        panel = pd.DataFrame(
            {
                "region_group": ["A"] * 5,
                "week_start": pd.to_datetime(
                    [
                        "2025-01-06",
                        "2025-01-20",
                        "2025-01-27",
                        "2025-02-03",
                        "2025-02-10",
                    ]
                ),
                "rain_mm_day": [100, 1, 2, 3, 4],
                "rain_mm_day_anomaly": [100, 1, 2, 3, 4],
                "shipments": [5, 999, 10, 20, 30],
                "shipments_anomaly": [5, 999, 10, 20, 30],
                "volume_mt": [0, 777, 100, 200, 300],
                "volume_mt_anomaly": [0, 777, 100, 200, 300],
            }
        )

        result = ca.calculate_lag_correlations(panel, max_lag=1)

        lag_one = result[result["rain_leads_weeks"] == 1].set_index("metric")
        self.assertEqual(lag_one.loc["shipments", "weeks"], 3)
        self.assertEqual(lag_one.loc["volume_mt", "weeks"], 3)
        self.assertAlmostEqual(lag_one.loc["shipments", "pearson_raw"], 1.0)
        self.assertAlmostEqual(lag_one.loc["shipments", "pearson_anomaly"], 1.0)
        self.assertAlmostEqual(lag_one.loc["volume_mt", "spearman_raw"], 1.0)
        self.assertEqual(lag_one.loc["shipments", "active_weeks"], 5)
        self.assertEqual(lag_one.loc["volume_mt", "active_weeks"], 4)

    def test_lag_correlations_reject_invalid_max_lag_values(self):
        panel = self._lag_panel(["2025-01-06"])

        for max_lag in (-1, 1.5, True, "2"):
            with self.subTest(max_lag=max_lag):
                with self.assertRaisesRegex(
                    ValueError,
                    "max_lag must be a non-negative integer",
                ):
                    ca.calculate_lag_correlations(panel, max_lag=max_lag)

    def test_lag_correlations_reject_bad_and_missing_week_start_with_rows(self):
        panel = self._lag_panel(
            ["bad-date", None, "2025-01-06"],
            index=[4, 8, 12],
        )

        with self.assertRaises(ValueError) as raised:
            ca.calculate_lag_correlations(panel)

        self.assertEqual(
            str(raised.exception),
            "Invalid or missing week_start at panel rows: 4, 8",
        )

    def test_lag_correlations_reject_timezone_aware_week_start(self):
        panel = self._lag_panel(
            pd.DatetimeIndex(["2025-01-06"], tz="Asia/Shanghai")
        )

        with self.assertRaisesRegex(
            ValueError, "week_start must be timezone-naive"
        ):
            ca.calculate_lag_correlations(panel)

    def test_lag_correlations_reject_non_monday_week_start_with_rows(self):
        panel = self._lag_panel(
            ["2025-01-07", "2025-01-13"],
            index=[6, 10],
        )

        with self.assertRaises(ValueError) as raised:
            ca.calculate_lag_correlations(panel)

        self.assertEqual(
            str(raised.exception),
            "week_start must contain Mondays; invalid panel rows: 6",
        )

    def test_lag_correlations_reject_duplicate_weeks_within_scope(self):
        panel = self._lag_panel(
            ["2025-01-06", "2025-01-06", "2025-01-06"],
            scopes=["A", "B", "A"],
            index=[1, 2, 3],
        )

        with self.assertRaises(ValueError) as raised:
            ca.calculate_lag_correlations(panel)

        self.assertEqual(
            str(raised.exception),
            "Duplicate week_start values within region_group at panel rows: 1, 3",
        )

    def test_monthly_correlations_aggregate_and_deseasonalize_by_region(self):
        panel = pd.DataFrame(
            {
                "region_group": ["A"] * 7 + ["B"] * 3,
                "week_start": pd.to_datetime(
                    [
                        "2024-01-01",
                        "2024-01-08",
                        "2024-02-05",
                        "2024-03-04",
                        "2025-01-06",
                        "2025-02-03",
                        "2025-03-03",
                        "2024-01-01",
                        "2024-02-05",
                        "2024-03-04",
                    ]
                ),
                "rain_mm_day": [0, 2, 2, 4, 3, 6, 5, 1, 2, 3],
                "shipments": [1, 2, 5, 4, 7, 6, 10, 3, 2, 1],
                "volume_mt": [10, 20, 40, 80, 50, 100, 90, 10, 20, 30],
            }
        )

        result = ca.calculate_monthly_correlations(panel)

        self.assertEqual(set(result["scope"]), {"A", "B"})
        self.assertEqual(set(result["metric"]), {"shipments", "volume_mt"})
        indexed = result.set_index(["scope", "metric"])
        monthly_rain = [1, 2, 4, 3, 6, 5]
        monthly_shipments = [3, 5, 4, 7, 6, 10]
        monthly_volume = [30, 40, 80, 50, 100, 90]
        rain_anomaly = [-1, -2, -0.5, 1, 2, 0.5]
        shipments_anomaly = [-2, -0.5, -3, 2, 0.5, 3]
        volume_anomaly = [-10, -30, -5, 10, 30, 5]
        self.assertAlmostEqual(
            indexed.loc[("A", "shipments"), "pearson_raw"],
            ca.correlation(monthly_rain, monthly_shipments),
        )
        self.assertAlmostEqual(
            indexed.loc[("A", "volume_mt"), "spearman_raw"],
            ca.correlation(monthly_rain, monthly_volume, rank=True),
        )
        self.assertAlmostEqual(
            indexed.loc[("A", "shipments"), "pearson_anomaly"],
            ca.correlation(rain_anomaly, shipments_anomaly),
        )
        self.assertAlmostEqual(
            indexed.loc[("A", "volume_mt"), "pearson_anomaly"],
            ca.correlation(rain_anomaly, volume_anomaly),
        )
        self.assertEqual(indexed.loc[("A", "shipments"), "months"], 6)
        self.assertAlmostEqual(indexed.loc[("B", "shipments"), "pearson_raw"], -1.0)
        self.assertAlmostEqual(indexed.loc[("B", "volume_mt"), "pearson_raw"], 1.0)
        self.assertEqual(
            list(result.columns),
            [
                "scope", "metric", "pearson_raw", "pearson_anomaly",
                "spearman_raw", "months", "analysis_start", "analysis_end",
            ],
        )
        self.assertEqual(
            set(result.loc[result["scope"].eq("A"), "analysis_start"]),
            {"2024-01-01"},
        )
        self.assertEqual(
            set(result.loc[result["scope"].eq("A"), "analysis_end"]),
            {"2025-03-03"},
        )
        self.assertEqual(
            set(result.loc[result["scope"].eq("B"), "analysis_start"]),
            {"2024-01-01"},
        )
        self.assertEqual(
            set(result.loc[result["scope"].eq("B"), "analysis_end"]),
            {"2024-03-04"},
        )

    def test_empty_correlation_tables_keep_provenance_schema(self):
        panel = pd.DataFrame(
            columns=[
                "region_group", "week_start", "rain_mm_day",
                "rain_mm_day_anomaly", "shipments", "shipments_anomaly",
                "volume_mt", "volume_mt_anomaly",
            ]
        )

        weekly = ca.calculate_lag_correlations(panel)
        monthly = ca.calculate_monthly_correlations(panel)

        self.assertTrue(weekly.empty)
        self.assertEqual(
            list(weekly.columns),
            [
                "scope", "metric", "rain_leads_weeks", "pearson_raw",
                "spearman_raw", "pearson_anomaly", "weeks", "active_weeks",
                "analysis_start", "analysis_end",
            ],
        )
        self.assertTrue(monthly.empty)
        self.assertEqual(
            list(monthly.columns),
            [
                "scope", "metric", "pearson_raw", "pearson_anomaly",
                "spearman_raw", "months", "analysis_start", "analysis_end",
            ],
        )


class NationalAnalysisTests(unittest.TestCase):
    def _regional_panel(self):
        return pd.DataFrame(
            {
                "region_group": ["B", "A", "B", "A"],
                "week_start": pd.to_datetime(
                    ["2025-01-06", "2025-01-06", "2025-01-13", "2025-01-13"]
                ),
                "rain_mm_day": [100.0, 10.0, 200.0, 20.0],
                "shipments": [1, 9, 1, 9],
                "volume_mt": [90.0, 10.0, 90.0, 10.0],
            }
        )

    def test_build_national_panel_uses_fixed_metric_specific_weights(self):
        national, weights = ca.build_national_panel(self._regional_panel())

        self.assertEqual(national["week_start"].tolist(), list(pd.to_datetime(
            ["2025-01-06", "2025-01-13"]
        )))
        self.assertEqual(national["shipments"].tolist(), [10, 10])
        self.assertEqual(national["volume_mt"].tolist(), [100.0, 100.0])
        self.assertEqual(weights["region_group"].tolist(), ["A", "B"])
        indexed = weights.set_index("region_group")
        self.assertAlmostEqual(indexed.loc["A", "shipments_weight"], 0.9)
        self.assertAlmostEqual(indexed.loc["A", "volume_mt_weight"], 0.1)
        self.assertAlmostEqual(weights["shipments_weight"].sum(), 1.0)
        self.assertAlmostEqual(weights["volume_mt_weight"].sum(), 1.0)
        self.assertAlmostEqual(national.loc[0, "rain_shipments"], 19.0)
        self.assertAlmostEqual(national.loc[0, "rain_volume_mt"], 91.0)

    def test_build_national_panel_rejects_invalid_common_panel(self):
        duplicate = pd.concat([self._regional_panel(), self._regional_panel().iloc[[0]]])
        with self.assertRaisesRegex(ValueError, "Duplicate region-week"):
            ca.build_national_panel(duplicate)

        missing = self._regional_panel()
        missing.loc[0, "rain_mm_day"] = float("nan")
        with self.assertRaisesRegex(ValueError, "Missing regional rainfall"):
            ca.build_national_panel(missing)

        for metric in ("shipments", "volume_mt"):
            with self.subTest(metric=metric):
                zero_weights = self._regional_panel()
                zero_weights[metric] = 0
                with self.assertRaisesRegex(ValueError, f"Zero total {metric}"):
                    ca.build_national_panel(zero_weights)

    def test_build_national_panel_rejects_negative_regional_weight_totals(self):
        for metric in ("shipments", "volume_mt"):
            with self.subTest(metric=metric):
                panel = self._regional_panel()
                panel.loc[panel["region_group"].eq("B"), metric] = -1

                with self.assertRaisesRegex(
                    ValueError,
                    f"Negative {metric} regional totals.*B",
                ):
                    ca.build_national_panel(panel)

    def test_build_national_panel_rejects_non_finite_regional_weight_totals(self):
        for metric in ("shipments", "volume_mt"):
            for invalid_value in (float("inf"), float("nan")):
                with self.subTest(metric=metric, invalid_value=invalid_value):
                    panel = self._regional_panel()
                    panel[metric] = panel[metric].astype(float)
                    panel.loc[panel["region_group"].eq("B"), metric] = invalid_value

                    with self.assertRaisesRegex(
                        ValueError,
                        f"Non-finite {metric} regional totals.*B",
                    ):
                        ca.build_national_panel(panel)

    def test_build_national_panel_rejects_overflowing_total_weight_basis(self):
        for metric in ("shipments", "volume_mt"):
            with self.subTest(metric=metric):
                panel = self._regional_panel()
                panel[metric] = 5e307

                with self.assertRaisesRegex(
                    ValueError,
                    f"Non-finite total {metric} weights",
                ):
                    ca.build_national_panel(panel)

    def test_national_lags_use_corresponding_rain_and_exact_dates(self):
        weeks = pd.to_datetime(
            [
                "2025-01-06", "2025-01-13", "2025-01-20",
                "2025-02-03", "2025-02-10", "2025-02-17",
            ]
        )
        national = pd.DataFrame(
            {
                "week_start": weeks,
                "rain_shipments": [1.0, 2.0, 999.0, 100.0, 200.0, 9999.0],
                "rain_volume_mt": [9.0, 8.0, 999.0, 7.0, 6.0, 9999.0],
                "shipments": [0.0, 4.0, 3.0, 0.0, 2.0, 1.0],
                "volume_mt": [0.0, 40.0, 30.0, 0.0, 20.0, 10.0],
            }
        )

        result = ca.calculate_national_lag_correlations(national, max_lag=1)

        self.assertEqual(
            list(result.columns),
            [
                "scope", "metric", "rain_leads_weeks", "pearson_raw",
                "spearman_raw", "pearson_anomaly", "weeks", "active_weeks",
                "analysis_start", "analysis_end",
            ],
        )
        self.assertEqual(set(result["scope"]), {"Philippines weighted"})
        self.assertEqual(set(result["analysis_start"]), {"2025-01-06"})
        self.assertEqual(set(result["analysis_end"]), {"2025-02-17"})
        lag_one = result[result["rain_leads_weeks"] == 1].set_index("metric")
        self.assertEqual(lag_one.loc["shipments", "weeks"], 4)
        self.assertEqual(lag_one.loc["volume_mt", "weeks"], 4)
        self.assertLess(lag_one.loc["shipments", "pearson_raw"], 0)
        self.assertGreater(lag_one.loc["volume_mt", "pearson_raw"], 0)
        self.assertAlmostEqual(lag_one.loc["shipments", "spearman_raw"], -1.0)
        self.assertAlmostEqual(lag_one.loc["volume_mt", "spearman_raw"], 1.0)

    def test_national_monthly_results_are_appendable_to_regional_schema(self):
        national = pd.DataFrame(
            {
                "week_start": pd.to_datetime(
                    [
                        "2024-01-01", "2024-02-05", "2024-03-04",
                        "2025-01-06", "2025-02-03", "2025-03-03",
                    ]
                ),
                "rain_shipments": [1, 2, 3, 4, 5, 6],
                "rain_volume_mt": [6, 5, 4, 3, 2, 1],
                "shipments": [1, 2, 3, 4, 5, 6],
                "volume_mt": [10, 20, 30, 40, 50, 60],
            }
        )

        national_result = ca.calculate_national_monthly_correlations(national)
        regional_columns = list(
            ca.calculate_monthly_correlations(
                self._regional_panel().assign(
                    rain_mm_day=lambda frame: frame["rain_mm_day"]
                )
            ).columns
        )

        self.assertEqual(list(national_result.columns), regional_columns)
        indexed = national_result.set_index("metric")
        self.assertAlmostEqual(indexed.loc["shipments", "pearson_raw"], 1.0)
        self.assertAlmostEqual(indexed.loc["volume_mt", "pearson_raw"], -1.0)
        self.assertEqual(set(national_result["analysis_start"]), {"2024-01-01"})
        self.assertEqual(set(national_result["analysis_end"]), {"2025-03-03"})


class IntegrationTests(unittest.TestCase):
    def test_print_summary_has_national_headlines_and_every_regional_metric(self):
        weekly_lags = pd.DataFrame(
            {
                "scope": [
                    "Philippines weighted", "Philippines weighted",
                    "Philippines weighted", "A", "A", "B", "B",
                ],
                "metric": [
                    "shipments", "shipments", "volume_mt",
                    "shipments", "volume_mt", "shipments", "volume_mt",
                ],
                "rain_leads_weeks": [0, 2, 0, 1, 3, 0, 4],
                "pearson_anomaly": [-0.2, -0.6, float("nan"), -0.4, -0.3, float("nan"), 0.2],
                "weeks": [260, 258, 260, 259, 257, 260, 256],
            }
        )

        with patch("builtins.print") as printer:
            ca.print_correlation_summary(weekly_lags)

        lines = [str(call.args[0]) for call in printer.call_args_list]
        self.assertEqual(
            lines[0],
            "Philippines weighted strongest de-seasonalized lag "
            "(minimum anomaly Pearson):",
        )
        self.assertIn("shipments: rain leads 2 week(s), r=-0.600, n=258", lines)
        self.assertIn("volume_mt: no negative correlation", lines)
        self.assertIn(
            "A | shipments | rain leads 1 week(s) | r=-0.400 | n=259",
            lines,
        )
        self.assertIn(
            "A | volume_mt | rain leads 3 week(s) | r=-0.300 | n=257",
            lines,
        )
        self.assertIn("B | shipments | no negative correlation", lines)
        self.assertIn("B | volume_mt | no negative correlation", lines)

    def test_print_summary_rejects_positive_only_and_all_nan_anomalies(self):
        weekly_lags = pd.DataFrame(
            {
                "scope": [
                    "Philippines weighted", "Philippines weighted", "A", "A",
                ],
                "metric": ["shipments", "volume_mt", "shipments", "volume_mt"],
                "rain_leads_weeks": [0, 1, 2, 3],
                "pearson_anomaly": [0.0, float("nan"), 0.4, float("nan")],
                "weeks": [260, 259, 258, 257],
            }
        )

        with patch("builtins.print") as printer:
            ca.print_correlation_summary(weekly_lags)

        lines = [str(call.args[0]) for call in printer.call_args_list]
        self.assertIn("shipments: no negative correlation", lines)
        self.assertIn("volume_mt: no negative correlation", lines)
        self.assertIn("A | shipments | no negative correlation", lines)
        self.assertIn("A | volume_mt | no negative correlation", lines)

    def test_region_configuration_rejects_region_order_missing_from_ports(self):
        ports = {"P1": {"region_group": "A"}}

        with self.assertRaises(ValueError) as raised:
            ca.validate_region_configuration(["A", "B"], ports)

        self.assertEqual(
            str(raised.exception),
            "Region configuration mismatch: missing from PORTS: B; "
            "extra in PORTS: none",
        )

    def test_region_configuration_rejects_ports_region_missing_from_order(self):
        ports = {
            "P1": {"region_group": "A"},
            "P2": {"region_group": "C"},
        }

        with self.assertRaises(ValueError) as raised:
            ca.validate_region_configuration(["A"], ports)

        self.assertEqual(
            str(raised.exception),
            "Region configuration mismatch: missing from PORTS: none; "
            "extra in PORTS: C",
        )

    def test_importing_module_does_not_import_rain(self):
        original_import = builtins.__import__

        def reject_rain_import(name, *args, **kwargs):
            if name == "rain":
                raise AssertionError("rain imported while loading correlation_analysis")
            return original_import(name, *args, **kwargs)

        spec = importlib.util.spec_from_file_location(
            "correlation_analysis_without_rain", ca.__file__
        )
        module = importlib.util.module_from_spec(spec)
        with patch("builtins.__import__", side_effect=reject_rain_import):
            spec.loader.exec_module(module)

    def test_help_does_not_import_rain(self):
        with (
            patch("correlation_analysis.importlib.import_module") as importer,
            self.assertRaises(SystemExit) as raised,
        ):
            ca.main(["--help"])

        self.assertEqual(raised.exception.code, 0)
        importer.assert_not_called()

    def test_complete_monday_weeks_stays_inside_calendar_years(self):
        weeks = ca.complete_monday_weeks(2021, 2025)

        self.assertEqual(weeks[0], pd.Timestamp("2021-01-04"))
        self.assertEqual(weeks[-1], pd.Timestamp("2025-12-22"))
        self.assertEqual(len(weeks), 260)
        self.assertTrue((weeks.weekday == 0).all())
        self.assertTrue(((weeks + pd.Timedelta(days=6)).year <= 2025).all())

    def test_complete_monday_weeks_validates_order_and_five_year_minimum(self):
        with self.assertRaisesRegex(ValueError, "end_year must be >= start_year"):
            ca.complete_monday_weeks(2025, 2024)
        with self.assertRaisesRegex(ValueError, "at least five calendar years"):
            ca.complete_monday_weeks(2022, 2025)

    def test_coverage_requires_every_day_and_expected_port(self):
        weeks = pd.DatetimeIndex(["2025-01-06"])
        rain_weekly = pd.DataFrame(
            {
                "region_group": ["A", "B"],
                "week_start": weeks.repeat(2),
                "rain_mm_day": [1.0, 2.0],
                "rain_days": [7, 6],
                "min_ports": [2, 1],
            }
        )
        expected = pd.DataFrame(
            {"region_group": ["A", "B"], "expected_ports": [2, 2]}
        )

        with self.assertRaisesRegex(ValueError, "B.*rain days.*ports"):
            ca.validate_rain_coverage(rain_weekly, ["A", "B"], weeks, expected)

    def test_merge_fails_clearly_when_region_week_rainfall_is_missing(self):
        shipments = pd.DataFrame(
            {
                "region_group": ["A", "B"],
                "week_start": pd.to_datetime(["2025-01-06"] * 2),
                "shipments": [1, 1],
                "volume_mt": [10, 20],
            }
        )
        rain_weekly = pd.DataFrame(
            {
                "region_group": ["A"],
                "week_start": pd.to_datetime(["2025-01-06"]),
                "rain_mm_day": [1.0],
                "rain_days": [7],
                "min_ports": [1],
            }
        )

        with self.assertRaisesRegex(ValueError, "Missing region-week rainfall: B 2025-01-06"):
            ca.merge_weekly_panels(shipments, rain_weekly)

    def test_load_rainfall_uses_validated_pickle_or_loader_without_writing(self):
        rain_frame = pd.DataFrame(
            {
                "date": pd.to_datetime(["2021-01-01"]),
                "port_name": ["P1"],
                "region_group": ["A"],
                "precipitation_mm": [1.0],
            }
        )
        ports = {"P1": {"region_group": "A"}}
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "rain.pkl"
            rain_frame.to_pickle(cache)
            loaded = ca.load_rainfall_data(2021, 2025, cache, ports=ports)
            assert_frame_equal(loaded, rain_frame)

            loader = unittest.mock.Mock(return_value=rain_frame)
            loaded_live = ca.load_rainfall_data(
                2021, 2025, ports=ports, loader=loader
            )
            loader.assert_called_once_with("2021-01-01", "2025-12-31")
            assert_frame_equal(loaded_live, rain_frame)
            self.assertEqual({path.name for path in Path(directory).iterdir()}, {"rain.pkl"})

    def test_load_rainfall_rejects_cache_dates_outside_selected_years(self):
        rain_frame = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-12-31"]),
                "port_name": ["P1"],
                "region_group": ["A"],
                "precipitation_mm": [1.0],
            }
        )
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "rain.pkl"
            rain_frame.to_pickle(cache)

            with self.assertRaisesRegex(ValueError, "outside 2021-2025"):
                ca.load_rainfall_data(
                    2021, 2025, cache, ports={"P1": {"region_group": "A"}}
                )

    def test_export_results_writes_exact_four_filenames(self):
        tables = {
            "weekly_lags": pd.DataFrame(
                {
                    "scope": ["A"],
                    "analysis_start": ["2025-01-06"],
                    "analysis_end": ["2025-02-10"],
                }
            ),
            "monthly": pd.DataFrame(
                {
                    "scope": ["Philippines weighted"],
                    "analysis_start": ["2024-01-01"],
                    "analysis_end": ["2025-03-03"],
                }
            ),
            "coverage": pd.DataFrame({"region_group": ["A"]}),
            "regional_weights": pd.DataFrame({"region_group": ["A"]}),
        }
        with TemporaryDirectory() as directory:
            paths = ca.export_results(tables, Path(directory))

            self.assertEqual(
                {path.name for path in Path(directory).glob("*.csv")},
                {
                    "weekly_lag_correlations.csv",
                    "monthly_correlations.csv",
                    "coverage.csv",
                    "regional_weights.csv",
                },
            )
            self.assertEqual(set(paths), set(tables))
            for key in ("weekly_lags", "monthly"):
                roundtrip = pd.read_csv(paths[key], dtype=str)
                assert_frame_equal(roundtrip, tables[key])

    def test_cli_orchestrates_complete_analysis_without_network(self):
        weeks = pd.date_range("2025-01-06", periods=4, freq="W-MON")
        shipments = pd.DataFrame(
            {
                "load_port": ["P1", "P2", "P1", "P2"],
                "load_start_date": [
                    "2025-01-06", "2025-01-06", "2025-01-13", "2025-01-13"
                ],
                "vsl_name": ["a", "b", "c", "d"],
                "voy_intake_mt": [10, 20, 30, 40],
            }
        )
        dates = [day for week in weeks for day in pd.date_range(week, periods=7)]
        rain_daily = pd.DataFrame(
            [
                {
                    "date": day,
                    "port_name": port,
                    "region_group": region,
                    "precipitation_mm": float(day.day + offset),
                }
                for day in dates
                for offset, (port, region) in enumerate((("P1", "A"), ("P2", "B")))
            ]
        )
        fake_ports = {
            "P1": {"region_group": "A"},
            "P2": {"region_group": "B"},
        }
        captured = {}

        def capture_export(tables, output_dir):
            captured.update(tables)
            captured["output_dir"] = output_dir
            return {key: output_dir / f"{key}.csv" for key in tables}

        rain_loader = unittest.mock.Mock()
        fake_rain = SimpleNamespace(
            PORTS=fake_ports,
            REGION_ORDER=["A", "B"],
            load_historical_data_cached=rain_loader,
        )
        with (
            patch.object(ca, "complete_monday_weeks", return_value=weeks),
            patch.object(ca.pd, "read_excel", return_value=shipments) as read_excel,
            patch.object(ca, "load_rainfall_data", return_value=rain_daily) as load_rain,
            patch.object(ca, "export_results", side_effect=capture_export),
            patch("builtins.print") as printer,
        ):
            result = ca.main(
                [
                    "--shipments-file", "shipments.xlsx",
                    "--rain-cache", "rain.pkl",
                    "--output-dir", "out",
                ],
                rain_module=fake_rain,
            )

        read_excel.assert_called_once_with(Path("shipments.xlsx"), sheet_name="Raw_Cleaned")
        load_rain.assert_called_once_with(
            2021,
            2025,
            Path("rain.pkl"),
            ports=fake_ports,
            loader=rain_loader,
        )
        self.assertEqual(captured["output_dir"], Path("out"))
        self.assertEqual(
            set(captured) - {"output_dir"},
            {"weekly_lags", "monthly", "coverage", "regional_weights"},
        )
        self.assertEqual(set(result["weekly_lags"]["scope"]), {"A", "B", "Philippines weighted"})
        printed = "\n".join(str(call.args[0]) for call in printer.call_args_list)
        self.assertIn("Philippines weighted strongest de-seasonalized lag", printed)
        self.assertIn("Regional strongest de-seasonalized lags", printed)
        self.assertIn("Coverage:", printed)


if __name__ == "__main__":
    unittest.main()
