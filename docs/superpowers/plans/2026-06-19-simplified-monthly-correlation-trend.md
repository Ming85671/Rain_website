# Simplified Monthly Correlation Trend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the correlation page's analysis-first controls with an English decision summary for monthly rainfall versus shipment volume and an actual rolling 24-month correlation trend.

**Architecture:** Add one reusable monthly-panel aggregator and a rolling raw-Pearson calculation to `correlation_analysis.py`, publish the rolling table beside the existing aggregate outputs, and pass it through the live/fallback page-data boundary. Keep detailed weekly charts below a simplified summary built from small, directly tested presentation helpers in `rain.py`.

**Tech Stack:** Python, pandas, Streamlit, Plotly, unittest

---

### Task 1: Calculate rolling monthly volume correlations

**Files:**
- Modify: `correlation_analysis.py:367-415`
- Test: `tests/test_correlation_analysis.py`

- [ ] **Step 1: Write failing rolling-window tests**

Add tests that build 30 complete monthly rows for one region, call `calculate_rolling_monthly_correlations(panel, window_months=24)`, and assert that the result contains seven points, the first point ends in month 24, every row reports 24 months, and each coefficient matches `correlation()` over the corresponding 24-row slice. Add a second test asserting that 23 valid months returns an empty dataframe with columns `scope`, `month`, `pearson_raw`, and `months`.

- [ ] **Step 2: Verify the tests fail for the missing API**

Run: `python3 -m unittest tests.test_correlation_analysis.CorrelationTests -v`

Expected: FAIL because `calculate_rolling_monthly_correlations` does not exist.

- [ ] **Step 3: Implement a shared monthly aggregator and rolling calculation**

Extract the existing month aggregation into `_aggregate_monthly_panel(panel)`. Implement:

```python
def calculate_rolling_monthly_correlations(panel, window_months=24):
    monthly = _aggregate_monthly_panel(panel)
    rows = []
    for scope, group in monthly.groupby("region_group", sort=False):
        group = group.sort_values("month").reset_index(drop=True)
        for end in range(window_months - 1, len(group)):
            window = group.iloc[end - window_months + 1:end + 1]
            rows.append({
                "scope": scope,
                "month": group.loc[end, "month"],
                "pearson_raw": correlation(window["rain_mm_day"], window["volume_mt"]),
                "months": _pair_count(window["rain_mm_day"], window["volume_mt"]),
            })
    return pd.DataFrame(rows, columns=ROLLING_MONTHLY_COLUMNS)
```

Validate `window_months >= 2` and keep existing monthly aggregate results unchanged.

- [ ] **Step 4: Verify monthly analysis tests pass**

Run: `python3 -m unittest tests.test_correlation_analysis.CorrelationTests -v`

Expected: PASS.

### Task 2: Publish rolling data through live and fallback paths

**Files:**
- Modify: `correlation_analysis.py:737-817`
- Modify: `rain.py:1012-1151`
- Modify: `correlation_output/rolling_monthly_correlations.csv`
- Test: `tests/test_correlation_analysis.py`
- Test: `tests/test_correlation_page.py`

- [ ] **Step 1: Write failing orchestration and page-data tests**

Update the correlation-table orchestration test to require a `rolling_monthly` table. Update export tests to require `rolling_monthly_correlations.csv`. Update page tests so `load_correlation_outputs`, `load_live_correlation_outputs`, `CorrelationPageData`, and fallback resolution all carry a fifth rolling dataframe.

- [ ] **Step 2: Verify the focused tests fail at the missing table boundary**

Run: `python3 -m unittest tests.test_correlation_analysis.IntegrationTests tests.test_correlation_page.CorrelationPageTests -v`

Expected: FAIL because rolling data is not yet returned or loaded.

- [ ] **Step 3: Add regional and national rolling outputs**

In `calculate_correlation_tables`, concatenate regional rolling output with rolling output from `_national_metric_panel(national_panel, "volume_mt")`, then add `rolling_monthly` to the returned dictionary. Add its filename to `RESULT_FILENAMES`. Extend `CorrelationPageData`, `load_correlation_outputs`, `load_live_correlation_outputs`, and `resolve_correlation_data` to carry the fifth dataframe and normalize its `month` column to string for committed outputs.

- [ ] **Step 4: Generate the committed fallback CSV**

Run:

```bash
python3 correlation_analysis.py \
  --shipments-file '/Users/a58475/resource/CODEX/Philippines/菲律宾镍矿装运量完成.xlsx' \
  --start-year 2021 \
  --end-year 2025 \
  --output-dir correlation_output
```

Expected: `correlation_output/rolling_monthly_correlations.csv` is written with 259 rows: 37 rolling points for each of six regions and the Philippines weighted scope.

- [ ] **Step 5: Verify focused pipeline tests pass**

Run: `python3 -m unittest tests.test_correlation_analysis.IntegrationTests tests.test_correlation_page.CorrelationPageTests -v`

Expected: PASS.

### Task 3: Build the simplified English decision summary

**Files:**
- Modify: `rain.py:1153-1439`
- Test: `tests/test_correlation_page.py`

- [ ] **Step 1: Write failing presentation-helper tests**

Add tests for `describe_correlation(value)` at `-0.10`, `-0.30`, `-0.50`, and `-0.70`, expecting no clear, weak, moderate, and strong negative relationship labels. Add a `monthly_volume_summary(monthly, scope)` test asserting it returns raw and de-seasonalized volume coefficients plus an English statement that a `-0.414` raw result and `-0.030` adjusted result are mainly seasonal. Add a chart test asserting `build_rolling_monthly_chart()` renders the selected scope, dates in order, the coefficient line, and a zero reference line.

- [ ] **Step 2: Verify presentation tests fail for missing helpers**

Run: `python3 -m unittest tests.test_correlation_page.CorrelationPageTests -v`

Expected: FAIL because the new helpers do not exist.

- [ ] **Step 3: Implement minimal English helpers and chart**

Implement `describe_correlation`, `monthly_volume_summary`, and `build_rolling_monthly_chart`. Use raw Pearson as the headline, `pearson_anomaly` as the seasonal diagnostic, and fixed `volume_mt` as the primary metric. Return an empty-state figure or message when fewer than 24 monthly pairs are available.

- [ ] **Step 4: Replace the main decision controls and summary layout**

Keep only the Region selector in the primary row. Render English cards for `Overall monthly correlation` and `What is driving it?`, followed by `Rolling 24-month correlation`. Explain that movement toward zero means a weakening relationship and may indicate that other factors are becoming more important. Preserve the existing weekly lag profile, heatmap, and method section below under `Detailed weekly analysis`.

- [ ] **Step 5: Verify page tests pass**

Run: `python3 -m unittest tests.test_correlation_page.CorrelationPageTests -v`

Expected: PASS.

### Task 4: Full verification, visual inspection, commit, and push

**Files:**
- Verify: `rain.py`
- Verify: `correlation_analysis.py`
- Verify: `correlation_output/*.csv`
- Verify: `tests/*.py`

- [ ] **Step 1: Run the complete test suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: all tests pass with zero failures and zero errors.

- [ ] **Step 2: Run syntax and diff checks**

Run: `python3 -m py_compile rain.py correlation_analysis.py`

Run: `git diff --check`

Expected: both commands exit successfully with no output.

- [ ] **Step 3: Render and inspect the Streamlit page**

Start the app with `python3 -m streamlit run rain.py --server.headless true`, open the local page, select the correlation page, and verify the English cards, actual rolling line, chart ordering, fallback warning, and responsive layout. Capture a screenshot as visual proof.

- [ ] **Step 4: Review scope and commit implementation**

Confirm that only the correlation calculation, correlation page, tests, generated correlation output, and approved docs changed. Stage those files explicitly and commit with `Simplify monthly rainfall correlation view`.

- [ ] **Step 5: Push and verify remote parity**

Run: `git push origin main`

Run: `git rev-parse HEAD` and `git rev-parse origin/main`

Expected: both revisions match.
