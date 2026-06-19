# Rolling Weekly Correlation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a selectable, line-only 52-week rolling Raw Pearson correlation trend below the existing monthly trend.

**Architecture:** Extend the analysis pipeline with a `rolling_weekly` table keyed by scope, metric, and week endpoint. Thread that table through fallback/live page data, then render it with a focused Plotly builder controlled by the existing Region and Metric selectors.

**Tech Stack:** Python, pandas, Plotly, Streamlit, unittest

---

### Task 1: Calculate rolling weekly correlations

**Files:**
- Modify: `correlation_analysis.py`
- Test: `tests/test_correlation_analysis.py`

- [ ] **Step 1: Write failing calculation tests**

Add tests that construct 56 Monday rows, call `calculate_rolling_weekly_correlations(panel, window_weeks=52)`, and assert ten rows total: five endpoints for each of `shipments` and `volume_mt`. For each metric, compare every result with `correlation(window["rain_mm_day"], window[metric])`. Add a 51-row test asserting the exact empty schema `scope, metric, week_start, pearson_raw, weeks`.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `python3 -m unittest tests.test_correlation_analysis.CorrelationTests.test_rolling_weekly_correlations_use_exact_52_week_windows tests.test_correlation_analysis.CorrelationTests.test_rolling_weekly_correlations_return_empty_schema_for_short_history`

Expected: failure because `calculate_rolling_weekly_correlations` does not exist.

- [ ] **Step 3: Implement the rolling calculation**

Add `ROLLING_WEEKLY_COLUMNS` and `calculate_rolling_weekly_correlations(panel, window_weeks=52)`. Validate that the window is an integer of at least two, normalize through `_validated_lag_panel`, group by scope, sort by Monday `week_start`, and emit one Raw Pearson row per valid endpoint and metric.

- [ ] **Step 4: Run the focused tests**

Run the command from Step 2.

Expected: both tests pass.

### Task 2: Publish the table through fallback and live paths

**Files:**
- Modify: `correlation_analysis.py`
- Modify: `rain.py`
- Modify: `tests/test_correlation_analysis.py`
- Modify: `tests/test_correlation_page.py`
- Regenerate: `correlation_output/rolling_weekly_correlations.csv`

- [ ] **Step 1: Write failing pipeline and loader tests**

Extend pipeline tests to require `tables["rolling_weekly"]`, both metrics, all regional scopes plus `Philippines weighted`, and 52 observations per row. Extend page fixtures and loader/live/fallback tests so `CorrelationPageData` carries `rolling_weekly` and the committed file loads with the expected schema.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `python3 -m unittest tests.test_correlation_analysis tests.test_correlation_page`

Expected: failures for the missing table, file, and data field.

- [ ] **Step 3: Implement pipeline propagation**

Calculate regional rolling-weekly rows directly. For the weighted national scope, call the same function once per metric on `_national_metric_panel(...)` and retain only that metric, matching the rolling-monthly pattern. Add `rolling_weekly` to `RESULT_FILENAMES`, export it, load it in `rain.py`, return it from the live loader, and carry it in `CorrelationPageData`.

- [ ] **Step 4: Regenerate the verified fallback output**

Run: `python3 correlation_analysis.py --shipments-file '/Users/a58475/resource/CODEX/Philippines/菲律宾镍矿装运量完成.xlsx' --start-year 2021 --end-year 2025 --output-dir correlation_output`

Expected: `correlation_output/rolling_weekly_correlations.csv` contains scope, metric, weekly endpoint, Raw Pearson, and 52-week counts.

- [ ] **Step 5: Run focused tests**

Run the command from Step 2.

Expected: all focused tests pass.

### Task 3: Render the line-only weekly trend

**Files:**
- Modify: `rain.py`
- Test: `tests/test_correlation_page.py`

- [ ] **Step 1: Write a failing chart test**

Add `test_rolling_weekly_chart_filters_metric_and_has_line_only_hover`. Supply mixed scopes and metrics, call `build_rolling_weekly_chart(data, "A", "shipments", "Shipment count")`, and assert the selected dates and coefficients, `mode == "lines"`, no marker mode, a zero reference line, and hover text containing scope, metric, correlation, and `52 complete weeks`.

- [ ] **Step 2: Run the chart test and confirm failure**

Run: `python3 -m unittest tests.test_correlation_page.CorrelationPageTests.test_rolling_weekly_chart_filters_metric_and_has_line_only_hover`

Expected: failure because the chart builder does not exist.

- [ ] **Step 3: Implement and place the chart**

Add `build_rolling_weekly_chart`, using a `go.Scatter` with `mode="lines"`, the existing correlation styling, a zero line, the full analysis range on the x-axis, and a custom hover template. Render the `Rolling 52-week correlation` section below the monthly callout and above `Detailed weekly analysis`; pass the selected scope, metric, and display label. Update the Method section to define the 52-week same-week calculation.

- [ ] **Step 4: Run the page tests**

Run: `python3 -m unittest tests.test_correlation_page`

Expected: all page tests pass.

### Task 4: Verify, commit, and publish

**Files:**
- Verify all modified files

- [ ] **Step 1: Run the full automated suite**

Run: `python3 -m unittest discover -s tests -p 'test_*.py'`

Expected: all tests pass.

- [ ] **Step 2: Run static checks**

Run: `python3 -m py_compile rain.py correlation_analysis.py`

Run: `git diff --check`

Expected: both commands exit successfully.

- [ ] **Step 3: Verify the rendered page**

Start Streamlit, open the correlation page, and verify both Metric options. Confirm the weekly chart sits below the monthly chart, spans the five-year x-axis, has no visible markers, and shows the required hover details.

- [ ] **Step 4: Commit and push**

Stage only the implementation, tests, plan, and regenerated rolling-weekly CSV. Commit with `Add rolling weekly correlation trend`, push `main`, and verify `HEAD` equals `origin/main`.
