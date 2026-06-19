# Detailed Monthly Correlation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a detailed monthly lag profile and regional heatmap that match the existing weekly analysis for lags 0 through 4 months.

**Architecture:** Produce a dedicated `monthly_lags` table from calendar-month aggregates, including raw Pearson, raw Spearman, and month-of-year-adjusted Pearson values. Thread it through live and fallback data, then generalize the existing chart builders with weekly defaults so monthly and weekly sections share one rendering implementation.

**Tech Stack:** Python, pandas, Plotly, Streamlit, unittest

---

### Task 1: Calculate monthly lag correlations

**Files:**
- Modify: `correlation_analysis.py`
- Test: `tests/test_correlation_analysis.py`

- [ ] **Step 1: Write failing monthly-lag tests**

Add a test with 24 monthly observations that calls `calculate_monthly_lag_correlations(panel, max_lag=4)`. Assert two metrics, lags 0–4, exact paired-month counts of 24 down to 20, and independently calculated Raw Pearson, Raw Spearman, and de-seasonalized Pearson values. Add an empty-panel test for the exact schema.

- [ ] **Step 2: Run tests and confirm the missing-function failure**

Run: `python3 -m unittest tests.test_correlation_analysis.CorrelationTests.test_monthly_lag_correlations_use_exact_calendar_months tests.test_correlation_analysis.CorrelationTests.test_monthly_lag_correlations_keep_empty_schema`

Expected: failure because `calculate_monthly_lag_correlations` is absent.

- [ ] **Step 3: Implement monthly lag calculation**

Add `MONTHLY_LAG_COLUMNS` and `calculate_monthly_lag_correlations(panel, max_lag=4)`. Reuse `_aggregate_monthly_panel`, calculate month-of-year anomalies, align future shipment values by exact `DateOffset(months=lag)`, and emit both metrics for every lag.

- [ ] **Step 4: Run focused tests**

Run the command from Step 2.

Expected: both tests pass.

### Task 2: Publish monthly lag data

**Files:**
- Modify: `correlation_analysis.py`
- Modify: `rain.py`
- Modify: `tests/test_correlation_analysis.py`
- Modify: `tests/test_correlation_page.py`
- Regenerate: `correlation_output/monthly_lag_correlations.csv`

- [ ] **Step 1: Write failing pipeline and loader tests**

Require `monthly_lags` in the analysis result and exported filenames. Extend page fixtures and live/fallback tests to carry the table through `CorrelationPageData`; assert the committed snapshot has 70 rows, seven scopes, both metrics, and lags 0–4.

- [ ] **Step 2: Run focused tests and confirm data-path failures**

Run: `python3 -m unittest tests.test_correlation_analysis tests.test_correlation_page`

Expected: failures for the missing table, file, and page-data field.

- [ ] **Step 3: Implement pipeline and page-data propagation**

Calculate regional monthly lags directly and weighted-national monthly lags with `_national_metric_panel`. Add `monthly_lags` to `RESULT_FILENAMES`, the live return tuple, fallback loader, resolver, and `CorrelationPageData`.

- [ ] **Step 4: Regenerate verified outputs**

Run: `python3 correlation_analysis.py --shipments-file '/Users/a58475/resource/CODEX/Philippines/菲律宾镍矿装运量完成.xlsx' --start-year 2021 --end-year 2025 --output-dir correlation_output`

Expected: `monthly_lag_correlations.csv` is created with 70 validated rows.

- [ ] **Step 5: Run focused tests**

Run the command from Step 2.

Expected: all focused tests pass.

### Task 3: Render matching detailed monthly charts

**Files:**
- Modify: `rain.py`
- Test: `tests/test_correlation_page.py`

- [ ] **Step 1: Write failing chart tests**

Add tests that call the lag-profile and heatmap builders with `rain_leads_months`, `months`, and `Monthly`. Assert x values 0–4, axis title `Rain leads shipments (months)`, hover suffix `m`, heatmap labels `0m`–`4m`, and titles containing `Monthly`.

- [ ] **Step 2: Run chart tests and confirm failure**

Run: `python3 -m unittest tests.test_correlation_page`

Expected: failures because the builders only support weekly columns and labels.

- [ ] **Step 3: Generalize chart builders and add the page section**

Keep weekly-compatible defaults while adding explicit lag-column, lag-unit, and period-title arguments. Render `Detailed monthly analysis` below the monthly callout and above `Rolling 52-week correlation`, using the same two-column widths and selected Region/Metric as the weekly section. Update Method copy to define 0–4 month and 0–4 week lags separately.

- [ ] **Step 4: Run page tests**

Run: `python3 -m unittest tests.test_correlation_page`

Expected: all page tests pass.

### Task 4: Verify and publish

**Files:**
- Verify all modified files and generated outputs

- [ ] **Step 1: Run full tests and static checks**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`

Run: `python3 -m py_compile rain.py correlation_analysis.py`

Run: `git diff --check`

Expected: all commands exit successfully.

- [ ] **Step 2: Verify the rendered page**

Open the correlation page and verify both metric options. Confirm matching two-column monthly and weekly sections, monthly labels `0m`–`4m`, weekly labels `0w`–`4w`, English titles, and selector synchronization.

- [ ] **Step 3: Commit and push**

Stage only the implementation, tests, plan, and generated monthly-lag snapshot. Commit with `Add detailed monthly correlation analysis`, push `main`, and verify `HEAD` equals `origin/main`.
