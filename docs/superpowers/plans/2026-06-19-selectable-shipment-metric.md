# Selectable Shipment Metric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one metric selector that switches the entire rainfall-correlation page between shipment count and shipment volume with exact metric-specific English titles.

**Architecture:** Extend the rolling monthly table to contain both existing correlation metrics, then pass the selected metric through small summary, chart, and copy helpers. Keep one synchronized selector so every page section always uses the same metric.

**Tech Stack:** Python, pandas, Streamlit, Plotly, unittest

---

### Task 1: Publish rolling trends for both metrics

**Files:**
- Modify: `correlation_analysis.py`
- Modify: `tests/test_correlation_analysis.py`
- Regenerate: `correlation_output/rolling_monthly_correlations.csv`

- [ ] **Step 1: Write failing tests**

Update rolling tests to require columns `scope`, `metric`, `month`, `pearson_raw`, and `months`, and assert that each 24-month window contains separate `shipments` and `volume_mt` coefficients calculated from the corresponding monthly series.

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_correlation_analysis.CorrelationTests -v`

Expected: FAIL because the current rolling result has no `metric` column and only calculates volume.

- [ ] **Step 3: Implement both metrics**

Change `ROLLING_MONTHLY_COLUMNS` to include `metric`. Inside each scope/window loop, append one row per metric:

```python
for metric in ("shipments", "volume_mt"):
    rows.append({
        "scope": scope,
        "metric": metric,
        "month": group.loc[end, "month"],
        "pearson_raw": correlation(window["rain_mm_day"], window[metric]),
        "months": _pair_count(window["rain_mm_day"], window[metric]),
    })
```

For the national panel, calculate rolling output separately through `_national_metric_panel()` for each metric and keep only that metric's rows.

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_correlation_analysis.CorrelationTests tests.test_correlation_analysis.IntegrationTests -v`

Expected: PASS.

- [ ] **Step 5: Regenerate fallback data**

Run:

```bash
python3 correlation_analysis.py \
  --shipments-file '/Users/a58475/resource/CODEX/Philippines/菲律宾镍矿装运量完成.xlsx' \
  --start-year 2021 --end-year 2025 \
  --output-dir correlation_output
```

Expected: 518 rolling rows, 259 per metric.

### Task 2: Synchronize page summaries, charts, and titles

**Files:**
- Modify: `rain.py`
- Modify: `tests/test_correlation_page.py`

- [ ] **Step 1: Write failing helper and title tests**

Update fixtures to include both rolling metrics. Require `monthly_metric_summary(monthly, scope, metric)` and `build_rolling_monthly_chart(rolling, scope, metric)` to select the requested metric. Add exact title tests:

```python
self.assertEqual(correlation_page_title("shipments"), "Rainfall impact on nickel ore shipments")
self.assertEqual(correlation_page_title("volume_mt"), "Rainfall impact on nickel ore volume")
```

- [ ] **Step 2: Verify RED**

Run: `python3 -m unittest tests.test_correlation_page.CorrelationPageTests -v`

Expected: FAIL because current helpers are volume-only and the title is fixed.

- [ ] **Step 3: Implement metric helpers and selector**

Add metric metadata:

```python
CORRELATION_METRICS = {
    "Shipment count": {"key": "shipments", "noun": "shipment count"},
    "Shipment volume (mt)": {"key": "volume_mt", "noun": "shipment volume"},
}
```

Generalize the monthly summary and rolling chart helpers to accept `metric`. Add `correlation_page_title(metric)`. Render `Region` and `Metric` selectors side by side with volume as the default, and pass the chosen metric to every card, trend, lag profile, heatmap, title, and explanatory sentence.

- [ ] **Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_correlation_page.CorrelationPageTests -v`

Expected: PASS.

### Task 3: Verify, commit, and push

**Files:**
- Verify all modified source, tests, generated CSV, spec, and plan files.

- [ ] **Step 1: Run full automated verification**

Run: `python3 -m unittest discover -s tests -v`

Run: `python3 -m py_compile rain.py correlation_analysis.py`

Run: `git diff --check`

Expected: all commands exit successfully.

- [ ] **Step 2: Verify both rendered selections**

Run Streamlit locally. Select `Shipment count` and verify the exact title `Rainfall impact on nickel ore shipments`; select `Shipment volume (mt)` and verify `Rainfall impact on nickel ore volume`. Confirm all cards and charts update with the selected metric.

- [ ] **Step 3: Commit intended files**

Stage source, tests, generated rolling CSV, spec, and plan explicitly. Commit with `Add selectable shipment correlation metric`.

- [ ] **Step 4: Push and verify parity**

Run: `git push origin main`, then verify `git rev-parse HEAD` equals `git rev-parse origin/main`.
