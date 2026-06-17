import math
import unittest

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

    def test_weekly_panel_excludes_out_of_range_and_invalid_rows(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": [
                    "2025-01-07",
                    "2025-01-08 06:30",
                    "2024-12-30",
                    "bad-date",
                    "2025-01-09",
                    "2025-01-10",
                ],
                "region_group": [
                    "Region A",
                    "Region A",
                    "Region A",
                    "Region A",
                    None,
                    "Region A",
                ],
                "vsl_name": ["One", "Two", "Earlier", "Bad date", "No region", None],
                "voy_intake_mt": ["10", "20", "999", "30", "40", "50"],
            }
        )
        weeks = pd.DatetimeIndex(["2025-01-06", "2025-01-13"])

        result = ca.build_shipment_weekly_panel(shipments, ["Region A"], weeks)

        self.assertEqual(result["shipments"].tolist(), [2, 0])
        self.assertEqual(result["volume_mt"].tolist(), [30.0, 0.0])

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
                "region_group": ["A", "A", "A", "A"],
                "port_name": ["P1", "P2", "P3", "P4"],
                "date": [
                    "2025-01-06",
                    "bad-date",
                    "2025-01-07",
                    "2025-01-08",
                ],
                "precipitation_mm": [1.0, "trace", None, float("inf")],
            },
            index=[4, 9, 15, 22],
        )

        with self.assertRaises(ValueError) as raised:
            ca.build_rain_weekly_panel(rain, ["2025-01-06"])

        self.assertEqual(
            str(raised.exception),
            "Invalid or missing precipitation_mm at rainfall rows: 9, 15, 22",
        )

    def test_build_rain_weekly_panel_drops_bad_dates_and_omits_missing_weeks(self):
        rain = pd.DataFrame(
            {
                "region_group": ["A", "A", "B"],
                "port_name": ["P1", "P1", "P2"],
                "date": ["not-a-date", "2025-01-07", "2025-01-20"],
                "precipitation_mm": [100.0, 3.0, 9.0],
            }
        )

        result = ca.build_rain_weekly_panel(
            rain,
            pd.to_datetime(["2025-01-06", "2025-01-13"]),
        )

        self.assertEqual(result["region_group"].tolist(), ["A"])
        self.assertEqual(result["week_start"].tolist(), [pd.Timestamp("2025-01-06")])
        self.assertEqual(result["rain_mm_day"].tolist(), [3.0])

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
    def test_correlation_drops_missing_pairs_before_pearson(self):
        result = ca.correlation([1.0, 2.0, None, 4.0], [2.0, 4.0, 100.0, 8.0])

        self.assertAlmostEqual(result, 1.0)

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


if __name__ == "__main__":
    unittest.main()
