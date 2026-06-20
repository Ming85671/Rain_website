# Overall Weekly Correlation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a five-year same-week weekly correlation card beside the existing overall monthly card.

**Architecture:** Read the weekly headline from the existing lag-zero aggregate row and summarize it through a focused helper. Render monthly and weekly headline cards side by side, with the existing monthly seasonality explanation in a separate full-width card.

**Tech Stack:** Python, pandas, Streamlit, unittest

---

### Task 1: Weekly summary calculation

**Files:**
- Modify: `tests/test_correlation_page.py`
- Modify: `rain.py`

- [ ] **Step 1: Write the failing test**

Add a test that passes multiple weekly lags and metrics to `weekly_metric_summary`, then requires the selected metric's lag-zero `pearson_raw`, its strength verdict, and the complete-week count.

- [ ] **Step 2: Verify the test fails**

Run: `python3 -m unittest tests.test_correlation_page.CorrelationPageTests.test_weekly_metric_summary_uses_all_complete_same_weeks`

Expected: fail because `weekly_metric_summary` does not exist.

- [ ] **Step 3: Implement the minimal helper**

Filter by scope, metric, and `rain_leads_weeks == 0`; require one row; return `raw`, `verdict`, and `weeks`.

- [ ] **Step 4: Verify the test passes**

Run the focused test again and expect `OK`.

### Task 2: Weekly headline card

**Files:**
- Modify: `tests/test_correlation_page.py`
- Modify: `rain.py`

- [ ] **Step 1: Add failing source assertions**

Require the page source to contain `Overall weekly correlation`, the all-complete-weeks explanation, and a call to `weekly_metric_summary`.

- [ ] **Step 2: Verify the assertions fail**

Run the relevant correlation page tests and confirm the new copy is absent.

- [ ] **Step 3: Implement the card layout**

Render equal monthly and weekly cards in the first row. Render the existing monthly `What is driving it?` content in a full-width card below them. Do not change charts or data files.

- [ ] **Step 4: Run verification**

Run `python3 -m unittest discover -s tests -p 'test_*.py'`, `python3 -m py_compile rain.py correlation_analysis.py`, and `git diff --check`.

### Task 3: Publish

**Files:**
- Verify: `rain.py`
- Verify: `tests/test_correlation_page.py`

- [ ] **Step 1: Inspect the rendered page**

Confirm both headline cards show the selected region and metric values without overflow, and that the driver card remains readable below them.

- [ ] **Step 2: Commit and push**

Stage only the implementation, tests, design, and plan. Commit, push `main`, and verify `HEAD` equals `origin/main`.
