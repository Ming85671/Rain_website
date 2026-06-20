import inspect
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
        self.rolling = pd.DataFrame(
            {
                "scope": ["Philippines weighted"] * 4,
                "metric": ["shipments", "shipments", "volume_mt", "volume_mt"],
                "month": ["2025-11-01", "2025-12-01"] * 2,
                "pearson_raw": [-0.42, -0.38, -0.45, -0.40],
                "months": [24] * 4,
            }
        )
        self.rolling_weekly = pd.DataFrame(
            {
                "scope": ["Philippines weighted"] * 4,
                "metric": ["shipments", "shipments", "volume_mt", "volume_mt"],
                "week_start": ["2025-12-15", "2025-12-22"] * 2,
                "pearson_raw": [-0.32, -0.30, -0.41, -0.39],
                "weeks": [52] * 4,
            }
        )
        self.monthly_lags = pd.DataFrame(
            {
                "scope": ["Philippines weighted"] * 10,
                "metric": ["shipments"] * 5 + ["volume_mt"] * 5,
                "rain_leads_months": list(range(5)) * 2,
                "pearson_raw": [-0.4, -0.3, -0.2, -0.1, 0.0] * 2,
                "spearman_raw": [-0.3, -0.2, -0.1, 0.0, 0.1] * 2,
                "pearson_anomaly": [-0.1, -0.2, -0.3, -0.2, -0.1] * 2,
                "months": [60, 59, 58, 57, 56] * 2,
                "analysis_start": ["2021-01-04"] * 10,
                "analysis_end": ["2025-12-22"] * 10,
            }
        )

    def test_correlation_sidebar_caption_describes_live_complete_week_refresh(self):
        self.assertEqual(
            rain.CORRELATION_SIDEBAR_CAPTION,
            "Live refresh · complete weeks only",
        )

    def test_committed_correlation_outputs_cover_verified_five_year_panel(self):
        (
            weekly,
            monthly,
            rolling,
            rolling_weekly,
            monthly_lags,
            coverage,
            weights,
        ) = (
            rain.load_correlation_outputs()
        )

        self.assertEqual(len(weekly), 70)
        self.assertEqual(len(monthly), 14)
        self.assertEqual(len(rolling), 518)
        self.assertEqual(set(rolling["metric"]), {"shipments", "volume_mt"})
        self.assertEqual(len(rolling_weekly), 2926)
        self.assertEqual(
            set(rolling_weekly["metric"]),
            {"shipments", "volume_mt"},
        )
        self.assertEqual(set(rolling_weekly["weeks"]), {52})
        self.assertEqual(rolling_weekly["week_start"].min(), "2021-12-27")
        self.assertEqual(rolling_weekly["week_start"].max(), "2025-12-22")
        self.assertEqual(len(monthly_lags), 70)
        self.assertEqual(set(monthly_lags["metric"]), {"shipments", "volume_mt"})
        self.assertEqual(set(monthly_lags["rain_leads_months"]), set(range(5)))
        self.assertEqual(len(set(monthly_lags["scope"])), 7)
        self.assertEqual(len(coverage), 6)
        self.assertEqual(len(weights), 6)
        self.assertEqual(set(weekly["analysis_start"]), {"2021-01-04"})
        self.assertEqual(set(weekly["analysis_end"]), {"2025-12-22"})
        self.assertEqual(set(rolling["months"]), {24})
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
            return_value=(
                self.weekly,
                monthly,
                self.rolling,
                self.rolling_weekly,
                self.monthly_lags,
                coverage,
                weights,
            ),
        ):
            result = rain.resolve_correlation_data(
                {"host": "db.example", "password": "secret"},
                today_key="2026-06-19",
            )

        self.assertEqual(result.source, "live")
        self.assertIsNone(result.warning)
        pd.testing.assert_frame_equal(result.weekly, self.weekly)
        pd.testing.assert_frame_equal(result.rolling_monthly, self.rolling)
        pd.testing.assert_frame_equal(result.rolling_weekly, self.rolling_weekly)
        pd.testing.assert_frame_equal(result.monthly_lags, self.monthly_lags)

    def test_load_live_correlation_outputs_uses_latest_completed_data_week(self):
        shipments = pd.DataFrame(
            {
                "load_start_date": ["2026-06-14", "2026-06-18"],
                "load_port": ["Surigao", "Surigao"],
                "vsl_name": ["A", "B"],
                "voy_intake_mt": [50000, 60000],
            }
        )
        rainfall = pd.DataFrame()
        tables = {
            "weekly_lags": self.weekly,
            "monthly": pd.DataFrame(),
            "rolling_monthly": self.rolling,
            "rolling_weekly": self.rolling_weekly,
            "monthly_lags": self.monthly_lags,
            "coverage": pd.DataFrame(),
            "regional_weights": pd.DataFrame(),
        }
        rain.load_live_correlation_outputs.clear()

        with (
            patch.object(rain, "load_live_shipments", return_value=shipments),
            patch.object(
                rain,
                "load_historical_data_cached",
                return_value=rainfall,
            ) as load_rain,
            patch.object(
                rain.correlation,
                "_validate_rainfall_data",
                return_value=rainfall,
            ),
            patch.object(
                rain.correlation,
                "calculate_correlation_tables",
                return_value=tables,
            ) as calculate,
        ):
            result = rain.load_live_correlation_outputs(
                (("host", "db.example"),),
                "2026-06-19",
            )

        self.assertIs(result[0], self.weekly)
        self.assertIs(result[2], self.rolling)
        self.assertIs(result[3], self.rolling_weekly)
        self.assertIs(result[4], self.monthly_lags)
        self.assertEqual(load_rain.call_args.args[:2], ("2021-01-01", "2026-06-14"))
        supplied_weeks = calculate.call_args.kwargs["weeks"]
        self.assertEqual(supplied_weeks[-1], pd.Timestamp("2026-06-08"))
        self.assertEqual(
            calculate.call_args.kwargs["weight_baseline_end"],
            "2025-12-31",
        )

    def test_resolve_correlation_data_falls_back_without_database_config(self):
        result = rain.resolve_correlation_data(None, today_key="2026-06-19")

        self.assertEqual(result.source, "fallback")
        self.assertIn("database", result.warning.lower())
        self.assertEqual(set(result.weekly["analysis_end"]), {"2025-12-22"})
        self.assertEqual(len(result.rolling_monthly), 518)
        self.assertEqual(len(result.rolling_weekly), 2926)
        self.assertEqual(len(result.monthly_lags), 70)

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

    def test_correlation_page_summary_uses_actual_window_and_source(self):
        coverage = pd.DataFrame(
            {
                "weeks": [284, 284],
                "expected_ports": [12, 18],
            }
        )
        weekly = self.weekly.copy()
        weekly["analysis_end"] = "2026-06-08"

        result = rain.correlation_page_summary(
            weekly,
            coverage,
            source="live",
        )

        self.assertEqual(result["analysis_start"], "2021-01-04")
        self.assertEqual(result["analysis_end"], "2026-06-08")
        self.assertEqual(result["weeks"], 284)
        self.assertEqual(result["ports"], 30)
        self.assertEqual(result["status"], "Live")

    def test_correlation_page_summary_labels_fallback_snapshot(self):
        coverage = pd.DataFrame({"weeks": [260], "expected_ports": [30]})

        result = rain.correlation_page_summary(
            self.weekly,
            coverage,
            source="fallback",
        )

        self.assertEqual(result["status"], "Verified fallback")

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

        title = figure.layout.title.text
        self.assertIn("Weekly lag profile<br>", title)
        self.assertIn(
            "<span style='font-size:14px'>Shipment count · "
            "Surigao-Dinagat-Caraga</span>",
            title,
        )
        self.assertGreaterEqual(figure.layout.margin.t, 150)
        self.assertEqual(figure.layout.legend.yanchor, "top")
        self.assertGreaterEqual(figure.layout.legend.y, 1.2)
        self.assertEqual(figure.layout.title.yanchor, "top")
        self.assertLessEqual(figure.layout.title.y, 0.94)

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

    def test_monthly_lag_profile_uses_month_labels_and_title(self):
        figure = rain.build_lag_profile_chart(
            self.monthly_lags,
            scope="Philippines weighted",
            metric="shipments",
            lag_column="rain_leads_months",
            lag_unit="months",
            period_label="Monthly",
        )

        self.assertEqual(list(figure.data[0].x), [0, 1, 2, 3, 4])
        self.assertEqual(
            list(figure.data[0].y),
            [-0.1, -0.2, -0.3, -0.2, -0.1],
        )
        self.assertEqual(
            figure.layout.xaxis.title.text,
            "Rain leads shipments (months)",
        )
        self.assertIn("Rain leads %{x}m", figure.data[0].hovertemplate)
        self.assertIn("Monthly lag profile<br>", figure.layout.title.text)
        self.assertIn(
            "<span style='font-size:14px'>Shipment count · "
            "Philippines weighted</span>",
            figure.layout.title.text,
        )
        self.assertGreaterEqual(figure.layout.margin.t, 150)

    def test_monthly_heatmap_uses_month_labels_and_title(self):
        monthly_lags = pd.DataFrame(
            {
                "scope": ["A"] * 5,
                "metric": ["shipments"] * 5,
                "rain_leads_months": list(range(5)),
                "pearson_anomaly": [-0.1, -0.2, -0.3, -0.2, -0.1],
            }
        )

        figure = rain.build_correlation_heatmap(
            monthly_lags,
            metric="shipments",
            coefficient="pearson_anomaly",
            regions=["A"],
            lag_column="rain_leads_months",
            lag_unit="months",
            period_label="Monthly",
        )

        heatmap = figure.data[0]
        self.assertEqual(list(heatmap.x), ["0m", "1m", "2m", "3m", "4m"])
        self.assertEqual(list(heatmap.z[0]), [-0.1, -0.2, -0.3, -0.2, -0.1])
        self.assertIn("Monthly regional lag correlation", figure.layout.title.text)

    def test_describe_correlation_uses_plain_english_strength_bands(self):
        self.assertEqual(
            rain.describe_correlation(-0.10),
            "No clear relationship",
        )
        self.assertEqual(
            rain.describe_correlation(-0.30),
            "Weak negative relationship",
        )
        self.assertEqual(
            rain.describe_correlation(-0.50),
            "Moderate negative relationship",
        )
        self.assertEqual(
            rain.describe_correlation(-0.70),
            "Strong negative relationship",
        )

    def test_monthly_metric_summary_uses_selected_metric(self):
        monthly = pd.DataFrame(
            {
                "scope": ["Philippines weighted"] * 2,
                "metric": ["shipments", "volume_mt"],
                "pearson_raw": [-0.500, -0.414],
                "pearson_anomaly": [-0.250, -0.030],
            }
        )

        result = rain.monthly_metric_summary(
            monthly,
            "Philippines weighted",
            "shipments",
        )

        self.assertEqual(result["raw"], -0.500)
        self.assertEqual(result["adjusted"], -0.250)
        self.assertEqual(result["verdict"], "Moderate negative relationship")
        self.assertIn("remains after normal seasonality", result["explanation"])

    def test_weekly_metric_summary_uses_all_complete_same_weeks(self):
        weekly = pd.DataFrame(
            {
                "scope": ["Philippines weighted"] * 4,
                "metric": ["shipments", "shipments", "volume_mt", "volume_mt"],
                "rain_leads_weeks": [0, 1, 0, 1],
                "pearson_raw": [-0.320, -0.410, -0.275, -0.360],
                "weeks": [260, 259, 260, 259],
            }
        )

        result = rain.weekly_metric_summary(
            weekly,
            "Philippines weighted",
            "volume_mt",
        )

        self.assertEqual(result["raw"], -0.275)
        self.assertEqual(result["weeks"], 260)
        self.assertEqual(result["verdict"], "Weak negative relationship")

    def test_correlation_page_renders_overall_weekly_summary(self):
        source = inspect.getsource(rain.render_correlation_page)

        self.assertIn("Overall weekly correlation", source)
        self.assertIn("weekly_metric_summary(weekly, scope, metric)", source)
        self.assertIn("all {weekly_summary[\"weeks\"]} complete weeks", source)

    def test_correlation_page_title_matches_selected_metric(self):
        self.assertEqual(
            rain.correlation_page_title("shipments"),
            "Rainfall impact on nickel ore shipments",
        )
        self.assertEqual(
            rain.correlation_page_title("volume_mt"),
            "Rainfall impact on nickel ore volume",
        )

    def test_rolling_monthly_chart_uses_selected_scope_and_zero_reference(self):
        rolling = pd.DataFrame(
            {
                "scope": ["A", "A", "A", "A", "B"],
                "metric": ["shipments", "shipments", "volume_mt", "volume_mt", "shipments"],
                "month": ["2025-01-01", "2025-02-01", "2025-01-01", "2025-02-01", "2025-02-01"],
                "pearson_raw": [-0.5, -0.3, 0.7, 0.6, 0.1],
                "months": [24] * 5,
            }
        )

        figure = rain.build_rolling_monthly_chart(rolling, "A", "shipments")

        self.assertEqual(list(figure.data[0].x), list(pd.to_datetime(["2025-01-01", "2025-02-01"])))
        self.assertEqual(list(figure.data[0].y), [-0.5, -0.3])
        self.assertEqual(figure.data[0].name, "24-month correlation")
        self.assertTrue(
            any(shape.y0 == 0 and shape.y1 == 0 for shape in figure.layout.shapes)
        )

    def test_rolling_weekly_chart_filters_metric_and_has_line_only_hover(self):
        rolling = pd.DataFrame(
            {
                "scope": ["A", "A", "A", "A", "B"],
                "metric": [
                    "shipments",
                    "shipments",
                    "volume_mt",
                    "volume_mt",
                    "shipments",
                ],
                "week_start": [
                    "2021-12-27",
                    "2022-01-03",
                    "2021-12-27",
                    "2022-01-03",
                    "2022-01-03",
                ],
                "pearson_raw": [-0.5, -0.3, 0.7, 0.6, 0.1],
                "weeks": [52] * 5,
            }
        )

        figure = rain.build_rolling_weekly_chart(
            rolling,
            "A",
            "shipments",
            "Shipment count",
        )

        trace = figure.data[0]
        self.assertEqual(
            list(trace.x),
            list(pd.to_datetime(["2021-12-27", "2022-01-03"])),
        )
        self.assertEqual(list(trace.y), [-0.5, -0.3])
        self.assertEqual(trace.mode, "lines")
        self.assertNotIn("markers", trace.mode)
        self.assertIn("Region: %{customdata[0]}", trace.hovertemplate)
        self.assertIn("Metric: %{customdata[1]}", trace.hovertemplate)
        self.assertIn("Correlation: %{y:.3f}", trace.hovertemplate)
        self.assertIn("%{customdata[2]} complete weeks", trace.hovertemplate)
        self.assertEqual(pd.Timestamp(figure.layout.xaxis.range[0]), pd.Timestamp("2021-01-04"))
        self.assertEqual(pd.Timestamp(figure.layout.xaxis.range[1]), pd.Timestamp("2022-01-03"))
        self.assertTrue(
            any(shape.y0 == 0 and shape.y1 == 0 for shape in figure.layout.shapes)
        )


if __name__ == "__main__":
    unittest.main()
