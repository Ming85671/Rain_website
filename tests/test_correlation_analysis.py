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


if __name__ == "__main__":
    unittest.main()
