import unittest
from unittest.mock import Mock, patch

import pandas as pd

import rain


class CorrelationPageTests(unittest.TestCase):
    def setUp(self):
        self.weekly = pd.DataFrame(
            {
                "scope": ["Philippines weighted"] * 5 + ["Surigao-Dinagat-Caraga"] * 5,
                "metric": ["shipments"] * 10,
                "rain_leads_weeks": list(range(5)) * 2,
                "pearson_raw": [-0.24, -0.30, -0.36, -0.27, -0.25, -0.32, -0.36, -0.42, -0.35, -0.30],
                "spearman_raw": [-0.22, -0.27, -0.35, -0.28, -0.27, -0.34, -0.38, -0.45, -0.37, -0.35],
                "pearson_anomaly": [0.03, -0.06, -0.21, -0.01, 0.03, 0.02, -0.05, -0.25, -0.05, 0.05],
                "weeks": [260, 259, 258, 257, 256] * 2,
                "active_weeks": [260] * 5 + [239] * 5,
                "analysis_start": ["2021-01-04"] * 10,
                "analysis_end": ["2025-12-22"] * 10,
            }
        )

    def test_committed_correlation_outputs_cover_verified_five_year_panel(self):
        weekly, monthly, coverage, weights = rain.load_correlation_outputs()

        self.assertEqual(len(weekly), 70)
        self.assertEqual(len(monthly), 14)
        self.assertEqual(len(coverage), 6)
        self.assertEqual(len(weights), 6)
        self.assertEqual(set(weekly["analysis_start"]), {"2021-01-04"})
        self.assertEqual(set(weekly["analysis_end"]), {"2025-12-22"})
        self.assertTrue(coverage["weeks"].eq(260).all())
        self.assertEqual(int(coverage["expected_ports"].sum()), 30)

    def test_load_live_shipments_queries_required_mysql_columns(self):
        expected = pd.DataFrame(
            {
                "load_start_date": ["2026-06-08"],
                "load_port": ["Surigao"],
                "vsl_name": ["Vessel A"],
                "voy_intake_mt": [55000],
            }
        )
        connection = Mock()

        with (
            patch.object(rain.mysql.connector, "connect", return_value=connection) as connect,
            patch.object(rain.pd, "read_sql", return_value=expected) as read_sql,
        ):
            result = rain.load_live_shipments(
                (("host", "db.example"), ("user", "reader"))
            )

        connect.assert_called_once_with(host="db.example", user="reader")
        query = read_sql.call_args.args[0]
        self.assertIn("load_start_date", query)
        self.assertIn("load_port", query)
        self.assertIn("vsl_name", query)
        self.assertIn("voy_intake_mt", query)
        self.assertIn("FROM axs", query)
        connection.close.assert_called_once_with()
        pd.testing.assert_frame_equal(result, expected)

    def test_load_live_shipments_rejects_missing_database_columns(self):
        connection = Mock()
        incomplete = pd.DataFrame({"load_start_date": ["2026-06-08"]})

        with (
            patch.object(rain.mysql.connector, "connect", return_value=connection),
            patch.object(rain.pd, "read_sql", return_value=incomplete),
            self.assertRaisesRegex(ValueError, "missing columns"),
        ):
            rain.load_live_shipments((("host", "db.example"),))

        connection.close.assert_called_once_with()

    def test_resolve_correlation_data_returns_live_tables(self):
        monthly = pd.DataFrame({"metric": ["shipments"]})
        coverage = pd.DataFrame({"region_group": ["A"]})
        weights = pd.DataFrame({"region_group": ["A"]})

        with patch.object(
            rain,
            "load_live_correlation_outputs",
            return_value=(self.weekly, monthly, coverage, weights),
        ):
            result = rain.resolve_correlation_data(
                {"host": "db.example", "password": "secret"},
                today_key="2026-06-19",
            )

        self.assertEqual(result.source, "live")
        self.assertIsNone(result.warning)
        pd.testing.assert_frame_equal(result.weekly, self.weekly)

    def test_resolve_correlation_data_falls_back_without_database_config(self):
        result = rain.resolve_correlation_data(None, today_key="2026-06-19")

        self.assertEqual(result.source, "fallback")
        self.assertIn("database", result.warning.lower())
        self.assertEqual(set(result.weekly["analysis_end"]), {"2025-12-22"})

    def test_resolve_correlation_data_sanitizes_live_failure(self):
        with patch.object(
            rain,
            "load_live_correlation_outputs",
            side_effect=RuntimeError("password=do-not-display"),
        ):
            result = rain.resolve_correlation_data(
                {"host": "db.example", "password": "secret"},
                today_key="2026-06-19",
            )

        self.assertEqual(result.source, "fallback")
        self.assertNotIn("do-not-display", result.warning)
        self.assertIn("verified snapshot", result.warning.lower())

    def test_correlation_kpis_use_same_week_and_strongest_negative_lag(self):
        result = rain.correlation_kpis(
            self.weekly,
            scope="Philippines weighted",
            metric="shipments",
            coefficient="pearson_anomaly",
        )

        self.assertEqual(result["same_week"], 0.03)
        self.assertEqual(result["strongest_lag"], 2)
        self.assertEqual(result["strongest_value"], -0.21)
        self.assertEqual(result["weeks"], 260)
        self.assertEqual(result["active_weeks"], 260)

    def test_correlation_kpis_report_no_negative_lag(self):
        positive = self.weekly.copy()
        positive["pearson_anomaly"] = 0.1

        result = rain.correlation_kpis(
            positive,
            scope="Philippines weighted",
            metric="shipments",
            coefficient="pearson_anomaly",
        )

        self.assertIsNone(result["strongest_lag"])
        self.assertIsNone(result["strongest_value"])

    def test_lag_profile_chart_contains_three_verified_series(self):
        figure = rain.build_lag_profile_chart(
            self.weekly,
            scope="Surigao-Dinagat-Caraga",
            metric="shipments",
        )

        self.assertEqual(
            [trace.name for trace in figure.data],
            ["De-seasonalized Pearson", "Raw Pearson", "Raw Spearman"],
        )
        self.assertEqual(list(figure.data[0].x), [0, 1, 2, 3, 4])
        self.assertEqual(list(figure.data[0].y), [0.02, -0.05, -0.25, -0.05, 0.05])

    def test_lag_profile_reserves_separate_space_for_title_and_wrapped_legend(self):
        figure = rain.build_lag_profile_chart(
            self.weekly,
            scope="Surigao-Dinagat-Caraga",
            metric="shipments",
        )

        self.assertGreaterEqual(figure.layout.margin.t, 120)
        self.assertEqual(figure.layout.legend.yanchor, "top")
        self.assertGreaterEqual(figure.layout.legend.y, 1.2)
        self.assertEqual(figure.layout.title.yanchor, "top")

    def test_heatmap_uses_region_order_and_selected_coefficient(self):
        figure = rain.build_correlation_heatmap(
            self.weekly,
            metric="shipments",
            coefficient="pearson_anomaly",
            regions=["Surigao-Dinagat-Caraga"],
        )

        heatmap = figure.data[0]
        self.assertEqual(list(heatmap.x), ["0w", "1w", "2w", "3w", "4w"])
        self.assertEqual(list(heatmap.y), ["Surigao-Dinagat-Caraga"])
        self.assertEqual(list(heatmap.z[0]), [0.02, -0.05, -0.25, -0.05, 0.05])


if __name__ == "__main__":
    unittest.main()
