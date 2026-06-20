# Lag Profile Title Clearance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the Plotly modebar from covering monthly and weekly lag-profile titles.

**Architecture:** Update the shared lag-profile builder so both periods receive a short first-line title and a smaller metric/region subtitle. Reserve enough top margin for the two-line title and existing legend while leaving all modebar controls enabled.

**Tech Stack:** Python, Plotly, Streamlit, unittest

---

### Task 1: Specify the two-line title layout

**Files:**
- Modify: `tests/test_correlation_page.py`
- Modify: `rain.py`

- [ ] **Step 1: Write a failing layout test**

Extend `test_lag_profile_reserves_separate_space_for_title_and_wrapped_legend` to require `<br>` in the title, a smaller subtitle span containing the metric and region, and a top margin of at least 150 pixels. Add the same assertions to the monthly lag-profile test so both period labels are covered.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `python3 -m unittest tests.test_correlation_page.CorrelationPageTests.test_lag_profile_reserves_separate_space_for_title_and_wrapped_legend tests.test_correlation_page.CorrelationPageTests.test_monthly_lag_profile_uses_month_labels_and_title`

Expected: failure because the current title is one line and the top margin is 130 pixels.

- [ ] **Step 3: Implement the shared layout fix**

Build the title as `{period_label} lag profile<br><span style='font-size:14px'>{metric_name} · {scope}</span>`, increase the top margin to at least 150 pixels, and position the legend below the two-line title. Do not alter modebar configuration, data traces, axes, or hover templates.

- [ ] **Step 4: Run focused and full tests**

Run the command from Step 2, then run `python3 -m unittest discover -s tests -p 'test_*.py'`.

Expected: all tests pass.

### Task 2: Verify and publish

**Files:**
- Verify: `rain.py`
- Verify: `tests/test_correlation_page.py`

- [ ] **Step 1: Run static checks**

Run: `python3 -m py_compile rain.py correlation_analysis.py`

Run: `git diff --check`

Expected: both commands exit successfully.

- [ ] **Step 2: Verify both rendered charts**

Open the correlation page at the two-column dashboard width. Move the pointer into the monthly and weekly lag profiles so the modebar is visible, then confirm the toolbar does not overlap either title or subtitle.

- [ ] **Step 3: Commit and push**

Stage only the plan, `rain.py`, and `tests/test_correlation_page.py`. Commit with `Prevent lag profile title overlap`, push `main`, and verify `HEAD` equals `origin/main`.
