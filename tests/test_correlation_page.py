import unittest

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
