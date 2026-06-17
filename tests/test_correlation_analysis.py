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


class WeeklyPanelTests(unittest.TestCase):
    def test_monday_start_normalizes_date_like_values(self):
        values = pd.Series(["2025-01-06 14:30", "2025-01-12", "not-a-date"])

        result = ca.monday_start(values)

        expected = pd.Series(
            pd.to_datetime(["2025-01-06", "2025-01-06", None])
        )
        assert_series_equal(result, expected)

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
                "voy_intake_mt": ["10", "invalid", "999", "30", "40", "50"],
            }
        )
        weeks = pd.DatetimeIndex(["2025-01-06", "2025-01-13"])

        result = ca.build_shipment_weekly_panel(shipments, ["Region A"], weeks)

        self.assertEqual(result["shipments"].tolist(), [2, 0])
        self.assertEqual(result["volume_mt"].tolist(), [10.0, 0.0])

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
