# Weekly Correlation Driver Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a weekly raw-versus-seasonally-adjusted explanation beside the existing monthly explanation.

**Architecture:** Extend the lag-zero weekly summary with `pearson_anomaly` and a period-specific interpretation. Render the monthly and weekly driver cards in equal Streamlit columns without altering the headline cards or chart calculations.

**Tech Stack:** Python, pandas, Streamlit, unittest

---

### Task 1: Weekly adjusted summary

**Files:**
- Modify: `tests/test_correlation_page.py`
- Modify: `rain.py`

- [ ] **Step 1: Write a failing summary test**

Add `pearson_anomaly` to the weekly fixture and require `adjusted` plus an explanation that says the normal wet season is the main driver when raw correlation is negative and adjusted correlation is near zero.

- [ ] **Step 2: Verify the test fails**

Run: `python3 -m unittest tests.test_correlation_page.CorrelationPageTests.test_weekly_metric_summary_uses_all_complete_same_weeks`

Expected: fail because the weekly summary does not return `adjusted` or `explanation`.

- [ ] **Step 3: Implement the weekly interpretation**

Read lag-zero `pearson_anomaly`, apply the existing 0.20 clarity threshold, and use `weeks` rather than months in every weekly sentence.

- [ ] **Step 4: Verify the focused test passes**

Run the focused test again and expect `OK`.

### Task 2: Parallel driver cards

**Files:**
- Modify: `tests/test_correlation_page.py`
- Modify: `rain.py`

- [ ] **Step 1: Add failing page-copy assertions**

Require `What is driving the weekly relationship?`, `Raw weekly`, and `Compares unusual weeks` in `render_correlation_page`.

- [ ] **Step 2: Verify the assertions fail**

Run the page-source test and confirm the weekly labels are absent.

- [ ] **Step 3: Render equal driver columns**

Place the existing monthly driver markup in the left column and the weekly raw/adjusted markup in the right column. Keep the current card classes and selected metric noun.

- [ ] **Step 4: Run full verification**

Run `python3 -m unittest discover -s tests -p 'test_*.py'`, `python3 -m py_compile rain.py correlation_analysis.py`, `git diff --check`, and the Streamlit page runner.

### Task 3: Publish

**Files:**
- Verify: `rain.py`
- Verify: `tests/test_correlation_page.py`

- [ ] **Step 1: Review the final diff**

Confirm the change is limited to weekly summary fields, the parallel driver-card markup, tests, and these documents.

- [ ] **Step 2: Commit and push**

Stage only the intended files, commit, push `main`, and verify `HEAD` equals `origin/main`.
