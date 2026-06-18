# Live Correlation Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recalculate rainfall-versus-shipment count and volume correlations from the live `axs` MySQL table and Open-Meteo through the latest conservative complete week, with a verified static fallback.

**Architecture:** Add reusable dynamic-window orchestration to `correlation_analysis.py`, then add a cached MySQL adapter and live/fallback selector to `rain.py`. Keep the existing chart functions and committed CSVs; the page receives either validated live tables or fallback tables plus explicit freshness metadata.

**Tech Stack:** Python 3, pandas, Streamlit, mysql-connector-python, Open-Meteo, unittest, unittest.mock

---

### Task 1: Dynamic complete-week calculation

**Files:**
- Modify: `correlation_analysis.py`
- Test: `tests/test_correlation_analysis.py`

- [ ] **Step 1: Write failing tests for the conservative cutoff**

Add tests that call `latest_analysis_week(shipments, today)` with a Friday `today`, shipment dates in the previous completed week, stale dates, and future dates. Assert that the returned Monday is the earlier of the latest completed Monday and the Monday containing the latest eligible shipment record. Assert that no eligible shipment date raises `ValueError`.

```python
def test_latest_analysis_week_uses_latest_completed_shipment_week(self):
    shipments = pd.DataFrame({"load_start_date": ["2026-06-10", "2026-06-14"]})
    result = ca.latest_analysis_week(shipments, today="2026-06-19")
    self.assertEqual(result, pd.Timestamp("2026-06-08"))

def test_latest_analysis_week_ignores_current_and_future_records(self):
    shipments = pd.DataFrame({"load_start_date": ["2026-06-14", "2026-06-18", "2026-07-01"]})
    result = ca.latest_analysis_week(shipments, today="2026-06-19")
    self.assertEqual(result, pd.Timestamp("2026-06-08"))
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python3 -m unittest tests.test_correlation_analysis.CorrelationAnalysisTests.test_latest_analysis_week_uses_latest_completed_shipment_week tests.test_correlation_analysis.CorrelationAnalysisTests.test_latest_analysis_week_ignores_current_and_future_records`

Expected: errors because `latest_analysis_week` does not exist.

- [ ] **Step 3: Implement dynamic week helpers**

Add:

```python
def latest_complete_week(today=None):
    today = pd.Timestamp.today().normalize() if today is None else pd.Timestamp(today).normalize()
    return today - pd.Timedelta(days=today.weekday() + 7)

def latest_analysis_week(shipments, today=None):
    latest_complete = latest_complete_week(today)
    dates = pd.to_datetime(shipments["load_start_date"], errors="coerce", format="mixed")
    eligible = dates[dates <= latest_complete + pd.Timedelta(days=6)]
    if eligible.empty:
        raise ValueError("No shipment records in a completed analysis week")
    return min(latest_complete, monday_start(eligible.max()))

def complete_monday_weeks_through(start_year, final_week):
    first_day = pd.Timestamp(year=start_year, month=1, day=1)
    first_monday = first_day + pd.Timedelta(days=(-first_day.weekday()) % 7)
    final_week = pd.Timestamp(final_week).normalize()
    if final_week.weekday() != 0:
        raise ValueError("final_week must be a Monday")
    return pd.date_range(first_monday, final_week, freq="W-MON")
```

- [ ] **Step 4: Run focused and complete correlation-analysis tests**

Run: `python3 -m unittest tests.test_correlation_analysis`

Expected: all tests pass.

### Task 2: Reusable dataframe orchestration and fixed baseline weights

**Files:**
- Modify: `correlation_analysis.py`
- Test: `tests/test_correlation_analysis.py`

- [ ] **Step 1: Write failing tests for live table calculation**

Add a synthetic six-year regional panel and assert that changing a 2026 shipment or volume value changes the corresponding correlation table. Assert that national weight columns are identical when 2026 values change because weights are calculated only from weeks before `2026-01-01`.

```python
tables = ca.calculate_correlation_tables(
    shipments, rainfall, regions, ports, weeks,
    weight_baseline_end="2025-12-31",
)
self.assertEqual(set(tables), {"weekly_lags", "monthly", "coverage", "regional_weights"})
```

- [ ] **Step 2: Run focused tests and verify RED**

Run the new `calculate_correlation_tables` tests.

Expected: errors because the orchestration function and baseline argument do not exist.

- [ ] **Step 3: Add fixed-weight support and reusable orchestration**

Change `build_national_panel(regional_panel, weight_panel=None)` so totals used for weights come from `weight_panel` while weekly national shipment/volume and rainfall series still cover the full `regional_panel`. Add:

```python
def calculate_correlation_tables(shipments, rainfall, regions, ports, weeks, weight_baseline_end="2025-12-31"):
    validate_region_configuration(regions, ports)
    mapped = map_shipment_regions(shipments, {name: value["region_group"] for name, value in ports.items()})
    shipment_weekly = build_shipment_weekly_panel(mapped, regions, weeks)
    rain_weekly = build_rain_weekly_panel(rainfall, weeks)
    coverage = validate_rain_coverage(rain_weekly, regions, weeks, expected_port_counts(ports))
    panel = add_weekly_anomalies(merge_weekly_panels(shipment_weekly, rain_weekly))
    baseline = panel[pd.to_datetime(panel["week_start"]) <= pd.Timestamp(weight_baseline_end)]
    national, weights = build_national_panel(panel, weight_panel=baseline)
    return {
        "weekly_lags": pd.concat([calculate_lag_correlations(panel), calculate_national_lag_correlations(national)], ignore_index=True),
        "monthly": pd.concat([calculate_monthly_correlations(panel), calculate_national_monthly_correlations(national)], ignore_index=True),
        "coverage": coverage,
        "regional_weights": weights,
    }
```

Refactor `main()` to call this function and preserve CLI behavior.

- [ ] **Step 4: Run the full analysis test module**

Run: `python3 -m unittest tests.test_correlation_analysis`

Expected: all tests pass.

### Task 3: Cached MySQL shipment source

**Files:**
- Modify: `rain.py`
- Modify: `requirements.txt`
- Test: `tests/test_correlation_page.py`

- [ ] **Step 1: Write failing tests for the query contract**

Patch the database connector and `pandas.read_sql`; assert that `load_live_shipments` requests `load_start_date`, `load_port`, `vsl_name`, and `voy_intake_mt` from `axs`, filters Philippine nickel ore, closes the connection, and rejects missing required columns.

```python
frame = rain.load_live_shipments({"host": "db", "user": "u"})
self.assertEqual(list(frame.columns), ["load_start_date", "load_port", "vsl_name", "voy_intake_mt"])
```

- [ ] **Step 2: Run focused tests and verify RED**

Run the new MySQL loader tests.

Expected: errors because `load_live_shipments` does not exist.

- [ ] **Step 3: Add the dependency and loader**

Add `mysql-connector-python` to `requirements.txt`. In `rain.py`, import `mysql.connector` and implement a six-hour cached loader using a tuple of sorted secret items as its hashable configuration argument. Query:

```sql
SELECT load_start_date, load_port, vsl_name, voy_intake_mt
FROM axs
WHERE load_country = 'Philippines'
  AND commodity LIKE '%NICKEL%'
ORDER BY load_start_date
```

Close the connection in `finally` and raise a sanitized `ValueError` for invalid result schemas.

- [ ] **Step 4: Run correlation page tests**

Run: `python3 -m unittest tests.test_correlation_page`

Expected: all tests pass.

### Task 4: Live calculation with explicit fallback metadata

**Files:**
- Modify: `rain.py`
- Test: `tests/test_correlation_page.py`

- [ ] **Step 1: Write failing live/fallback selector tests**

Patch the shipment loader, rainfall loader, and calculation function. Assert that live success returns `source="live"` with the dynamic analysis end. Assert that missing secrets and raised exceptions return the committed tables with `source="fallback"` and a non-secret warning.

```python
result = rain.resolve_correlation_data(database_config=None)
self.assertEqual(result.source, "fallback")
self.assertIn("database", result.warning.lower())
```

- [ ] **Step 2: Run focused tests and verify RED**

Run the new selector tests.

Expected: errors because `CorrelationPageData` and `resolve_correlation_data` do not exist.

- [ ] **Step 3: Implement live calculation and fallback**

Add a `NamedTuple` or frozen dataclass containing `weekly`, `monthly`, `coverage`, `weights`, `source`, and `warning`. Implement a six-hour cached `load_live_correlation_outputs(config_items, today_key)` that:

- loads shipment rows;
- obtains `latest_analysis_week` and dynamic weeks from 2021;
- loads Open-Meteo rainfall from `2021-01-01` through the final Sunday;
- calls `calculate_correlation_tables` with fixed baseline end `2025-12-31`.

Implement `resolve_correlation_data(database_config)` to catch expected live-source/validation exceptions, load committed outputs, and return a sanitized fallback warning.

- [ ] **Step 4: Run page and analysis tests**

Run: `python3 -m unittest tests.test_correlation_page tests.test_correlation_analysis`

Expected: all tests pass.

### Task 5: Dynamic page freshness UI

**Files:**
- Modify: `rain.py`
- Test: `tests/test_correlation_page.py`

- [ ] **Step 1: Write failing tests for display metadata**

Extract a `correlation_page_summary(weekly, coverage, source)` helper and assert that it returns the real start/end dates, complete-week count, port count, and `Live` or `Verified fallback` status without hard-coded `2021-2025` text.

- [ ] **Step 2: Run focused tests and verify RED**

Run the new summary tests.

Expected: failure because the helper does not exist.

- [ ] **Step 3: Update page rendering**

Use `resolve_correlation_data` in `render_correlation_page`. Render a warning only for fallback mode. Replace the fixed subtitle with:

```text
2021-01-04 to YYYY-MM-DD · N complete weeks · 30 ports · 6 regions · Live
```

Keep all filters, KPIs, charts, and interpretation copy otherwise unchanged.

- [ ] **Step 4: Run page tests**

Run: `python3 -m unittest tests.test_correlation_page`

Expected: all tests pass.

### Task 6: Documentation and complete verification

**Files:**
- Modify: `README.md`
- Verify: all project tests and local Streamlit rendering

- [ ] **Step 1: Document deployment secrets and refresh behavior**

Document that Rain needs the same `[database]` secret block as data-analysis, refreshes every six hours, uses complete weeks only, and falls back to committed results when live validation fails. Do not include real credentials.

- [ ] **Step 2: Run static and automated verification**

Run:

```bash
git diff --check
python3 -m unittest discover -s tests
```

Expected: zero diff errors and all tests pass.

- [ ] **Step 3: Run the app and visually verify both modes**

Start Streamlit without local secrets and confirm the fallback warning, accurate snapshot date, and existing charts render. Use mocked or test-level live data to verify the dynamic summary because production credentials are intentionally unavailable locally.

- [ ] **Step 4: Review the final diff**

Confirm only `correlation_analysis.py`, `rain.py`, `requirements.txt`, `README.md`, tests, and the approved spec/plan are changed. Leave `.DS_Store` untracked and untouched.
