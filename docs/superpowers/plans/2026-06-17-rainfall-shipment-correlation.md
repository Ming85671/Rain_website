# Rainfall and Shipment Correlation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested command-line analysis that independently measures rainfall correlation with Philippine nickel ore shipment count and shipment volume over 2021-2025.

**Architecture:** Keep statistical transformations in a standalone `correlation_analysis.py` module that accepts dataframes and imports the existing `rain.PORTS` mapping as its location source of truth. The CLI loads the workbook and Open-Meteo data, builds complete regional weekly panels, calculates raw and de-seasonalized weekly correlations with 0-4 week lags, adds a monthly robustness view, and exports tidy CSV files. Streamlit rendering remains outside this implementation.

**Tech Stack:** Python 3, pandas, NumPy, unittest, existing Open-Meteo loader in `rain.py`.

---

## File structure

- Create `correlation_analysis.py`: dataframe transformations, correlation calculations, validation, CLI, and CSV export.
- Create `tests/test_correlation_analysis.py`: deterministic unit and integration-style tests with synthetic data.
- Modify `.gitignore`: ignore Python bytecode and generated correlation output/cache directories.
- Modify `README.md`: document the analysis command, inputs, outputs, and interpretation boundaries.

### Task 1: Port mapping and complete weekly panels

**Files:**
- Create: `correlation_analysis.py`
- Create: `tests/test_correlation_analysis.py`

- [ ] **Step 1: Write failing tests for aliases, unmapped ports, weekly alignment, and zero weeks**

```python
import unittest
import pandas as pd

import correlation_analysis as ca


class WeeklyPanelTests(unittest.TestCase):
    def test_map_shipment_regions_applies_alias_and_rejects_unknown_ports(self):
        shipments = pd.DataFrame({"load_port": ["Hinituan & Talavera Islands"]})
        port_map = {"Hinituan&Talavera Islands": "Surigao"}
        mapped = ca.map_shipment_regions(shipments, port_map)
        self.assertEqual(mapped.loc[0, "region_group"], "Surigao")

        with self.assertRaisesRegex(ValueError, "Unknown Port"):
            ca.map_shipment_regions(
                pd.DataFrame({"load_port": ["Unknown Port"]}), port_map
            )

    def test_build_shipment_weekly_panel_uses_monday_and_fills_zero_week(self):
        shipments = pd.DataFrame({
            "load_start_date": ["2025-01-07", "2025-01-08"],
            "region_group": ["Region A", "Region A"],
            "vsl_name": ["One", "Two"],
            "voy_intake_mt": [10.0, 20.0],
        })
        weeks = pd.date_range("2025-01-06", "2025-01-13", freq="W-MON")
        result = ca.build_shipment_weekly_panel(shipments, ["Region A"], weeks)
        self.assertEqual(result["week_start"].tolist(), list(weeks))
        self.assertEqual(result["shipments"].tolist(), [2, 0])
        self.assertEqual(result["volume_mt"].tolist(), [30.0, 0.0])
```

- [ ] **Step 2: Run tests and confirm the module is missing**

Run: `python3 -m unittest tests.test_correlation_analysis.WeeklyPanelTests -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'correlation_analysis'`.

- [ ] **Step 3: Implement port mapping and weekly shipment aggregation**

```python
import argparse
from pathlib import Path

import pandas as pd

import rain


PORT_ALIASES = {
    "Hinituan & Talavera Islands": "Hinituan&Talavera Islands",
}


def map_shipment_regions(shipments, port_region_map):
    out = shipments.copy()
    out["port_key"] = out["load_port"].replace(PORT_ALIASES)
    out["region_group"] = out["port_key"].map(port_region_map)
    unknown = sorted(out.loc[out["region_group"].isna(), "load_port"].unique())
    if unknown:
        raise ValueError(f"Unmapped shipment ports: {', '.join(unknown)}")
    return out


def monday_start(values):
    dates = pd.to_datetime(values, errors="coerce")
    return (dates - pd.to_timedelta(dates.dt.weekday, unit="D")).dt.normalize()


def build_shipment_weekly_panel(shipments, regions, weeks):
    out = shipments.copy()
    out["load_start_date"] = pd.to_datetime(out["load_start_date"], errors="coerce")
    out["voy_intake_mt"] = pd.to_numeric(out["voy_intake_mt"], errors="coerce").fillna(0)
    out = out.dropna(subset=["load_start_date", "region_group", "vsl_name"])
    out["week_start"] = monday_start(out["load_start_date"])
    index = pd.MultiIndex.from_product(
        [regions, weeks], names=["region_group", "week_start"]
    )
    return (
        out.groupby(["region_group", "week_start"])
        .agg(shipments=("vsl_name", "size"), volume_mt=("voy_intake_mt", "sum"))
        .reindex(index, fill_value=0)
        .reset_index()
    )
```

- [ ] **Step 4: Run the focused tests**

Run: `python3 -m unittest tests.test_correlation_analysis.WeeklyPanelTests -v`

Expected: 2 tests pass.

- [ ] **Step 5: Commit the first unit**

```bash
git add correlation_analysis.py tests/test_correlation_analysis.py
git commit -m "feat: build regional shipment weekly panel"
```

### Task 2: Rainfall panel and seasonal adjustment

**Files:**
- Modify: `correlation_analysis.py`
- Modify: `tests/test_correlation_analysis.py`

- [ ] **Step 1: Write failing rainfall and anomaly tests**

```python
class RainfallPanelTests(unittest.TestCase):
    def test_build_rain_weekly_panel_averages_ports_then_days(self):
        rain = pd.DataFrame({
            "region_group": ["A", "A", "A", "A"],
            "port_name": ["P1", "P2", "P1", "P2"],
            "date": ["2025-01-06", "2025-01-06", "2025-01-07", "2025-01-07"],
            "precipitation_mm": [2.0, 6.0, 4.0, 8.0],
        })
        result = ca.build_rain_weekly_panel(rain, pd.DatetimeIndex(["2025-01-06"]))
        self.assertEqual(result.loc[0, "rain_mm_day"], 5.0)
        self.assertEqual(result.loc[0, "rain_days"], 2)
        self.assertEqual(result.loc[0, "min_ports"], 2)

    def test_add_weekly_anomalies_centers_each_region_iso_week(self):
        panel = pd.DataFrame({
            "region_group": ["A", "A"],
            "week_start": pd.to_datetime(["2024-01-01", "2025-12-30"]),
            "rain_mm_day": [2.0, 6.0],
            "shipments": [1.0, 5.0],
            "volume_mt": [10.0, 30.0],
        })
        result = ca.add_weekly_anomalies(panel)
        self.assertEqual(result["rain_mm_day_anomaly"].tolist(), [-2.0, 2.0])
        self.assertEqual(result["shipments_anomaly"].tolist(), [-2.0, 2.0])
```

- [ ] **Step 2: Run tests and confirm missing functions**

Run: `python3 -m unittest tests.test_correlation_analysis.RainfallPanelTests -v`

Expected: FAIL with missing `build_rain_weekly_panel`.

- [ ] **Step 3: Implement rainfall aggregation and ISO-week anomalies**

```python
def build_rain_weekly_panel(rain, weeks):
    out = rain.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["precipitation_mm"] = pd.to_numeric(out["precipitation_mm"], errors="coerce")
    out = out.dropna(subset=["region_group", "port_name", "date", "precipitation_mm"])
    out["week_start"] = monday_start(out["date"])
    out = out[out["week_start"].isin(weeks)]
    daily = out.groupby(["region_group", "date", "week_start"], as_index=False).agg(
        rain_mm_day=("precipitation_mm", "mean"),
        port_count=("port_name", "nunique"),
    )
    return daily.groupby(["region_group", "week_start"], as_index=False).agg(
        rain_mm_day=("rain_mm_day", "mean"),
        rain_days=("date", "nunique"),
        min_ports=("port_count", "min"),
    )


def add_weekly_anomalies(panel):
    out = panel.copy()
    out["iso_week"] = out["week_start"].dt.isocalendar().week.astype(int)
    for column in ["rain_mm_day", "shipments", "volume_mt"]:
        baseline = out.groupby(["region_group", "iso_week"])[column].transform("mean")
        out[f"{column}_anomaly"] = out[column] - baseline
    return out
```

- [ ] **Step 4: Run all correlation tests**

Run: `python3 -m unittest tests.test_correlation_analysis -v`

Expected: 4 tests pass.

- [ ] **Step 5: Commit rainfall transformations**

```bash
git add correlation_analysis.py tests/test_correlation_analysis.py
git commit -m "feat: build weekly rainfall and anomaly panels"
```

### Task 3: Independent metrics, lags, and monthly robustness

**Files:**
- Modify: `correlation_analysis.py`
- Modify: `tests/test_correlation_analysis.py`

- [ ] **Step 1: Write failing tests for metric separation and lag direction**

```python
class CorrelationTests(unittest.TestCase):
    def test_calculate_lags_returns_separate_shipment_and_volume_rows(self):
        panel = pd.DataFrame({
            "scope": ["A"] * 5,
            "week_start": pd.date_range("2025-01-06", periods=5, freq="W-MON"),
            "rain_mm_day": [1, 2, 3, 4, 5],
            "rain_mm_day_anomaly": [1, 2, 3, 4, 5],
            "shipments": [0, 0, 5, 4, 3],
            "shipments_anomaly": [0, 0, 5, 4, 3],
            "volume_mt": [0, 0, 50, 40, 30],
            "volume_mt_anomaly": [0, 0, 50, 40, 30],
        })
        result = ca.calculate_lag_correlations(panel, "scope", max_lag=2)
        self.assertEqual(set(result["metric"]), {"shipments", "volume_mt"})
        lag_two = result[result["rain_leads_weeks"] == 2]
        self.assertTrue((lag_two["pearson_raw"] < 0).all())

    def test_spearman_uses_ranks_without_scipy(self):
        self.assertEqual(ca.correlation([1, 2, 100], [10, 20, 30], rank=True), 1.0)
```

- [ ] **Step 2: Run the tests and verify missing correlation functions**

Run: `python3 -m unittest tests.test_correlation_analysis.CorrelationTests -v`

Expected: FAIL with missing `calculate_lag_correlations`.

- [ ] **Step 3: Implement Pearson, rank correlation, lags, and monthly summaries**

```python
def correlation(left, right, rank=False):
    pairs = pd.DataFrame({"left": left, "right": right}).dropna()
    if len(pairs) < 3 or pairs["left"].nunique() < 2 or pairs["right"].nunique() < 2:
        return float("nan")
    if rank:
        pairs = pairs.rank(method="average")
    return float(pairs["left"].corr(pairs["right"]))


def calculate_lag_correlations(panel, scope_column="region_group", max_lag=4):
    rows = []
    for scope, group in panel.groupby(scope_column, sort=False):
        group = group.sort_values("week_start")
        for metric in ["shipments", "volume_mt"]:
            for lag in range(max_lag + 1):
                rows.append({
                    "scope": scope,
                    "metric": metric,
                    "rain_leads_weeks": lag,
                    "pearson_raw": correlation(
                        group["rain_mm_day"], group[metric].shift(-lag)
                    ),
                    "spearman_raw": correlation(
                        group["rain_mm_day"], group[metric].shift(-lag), rank=True
                    ),
                    "pearson_anomaly": correlation(
                        group["rain_mm_day_anomaly"],
                        group[f"{metric}_anomaly"].shift(-lag),
                    ),
                    "weeks": int(len(group) - lag),
                    "active_weeks": int((group[metric] > 0).sum()),
                })
    return pd.DataFrame(rows)
```

```python
def calculate_monthly_correlations(panel):
    monthly = panel.assign(
        month=panel["week_start"].dt.to_period("M").dt.to_timestamp()
    ).groupby(["region_group", "month"], as_index=False).agg(
        rain_mm_day=("rain_mm_day", "mean"),
        shipments=("shipments", "sum"),
        volume_mt=("volume_mt", "sum"),
    )
    monthly["month_of_year"] = monthly["month"].dt.month
    for column in ["rain_mm_day", "shipments", "volume_mt"]:
        baseline = monthly.groupby(["region_group", "month_of_year"])[column].transform("mean")
        monthly[f"{column}_anomaly"] = monthly[column] - baseline
    rows = []
    for region, group in monthly.groupby("region_group", sort=False):
        for metric in ["shipments", "volume_mt"]:
            rows.append({
                "scope": region,
                "metric": metric,
                "months": len(group),
                "pearson_raw": correlation(group["rain_mm_day"], group[metric]),
                "pearson_anomaly": correlation(
                    group["rain_mm_day_anomaly"], group[f"{metric}_anomaly"]
                ),
            })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run all correlation tests**

Run: `python3 -m unittest tests.test_correlation_analysis -v`

Expected: 6 tests pass.

- [ ] **Step 5: Commit statistical calculations**

```bash
git add correlation_analysis.py tests/test_correlation_analysis.py
git commit -m "feat: calculate lagged and seasonal correlations"
```

### Task 4: Fixed-weight national analysis

**Files:**
- Modify: `correlation_analysis.py`
- Modify: `tests/test_correlation_analysis.py`

- [ ] **Step 1: Write a failing test that proves fixed weights are used**

```python
class NationalAggregationTests(unittest.TestCase):
    def test_build_national_panel_uses_metric_specific_fixed_weights(self):
        panel = pd.DataFrame({
            "region_group": ["A", "A", "B", "B"],
            "week_start": pd.to_datetime(["2025-01-06", "2025-01-13"] * 2),
            "rain_mm_day": [10.0, 20.0, 100.0, 200.0],
            "shipments": [9, 9, 1, 1],
            "volume_mt": [10.0, 10.0, 90.0, 90.0],
        })
        national, weights = ca.build_national_panel(panel)
        self.assertAlmostEqual(weights["shipments"]["A"], 0.9)
        self.assertAlmostEqual(weights["volume_mt"]["A"], 0.1)
        self.assertAlmostEqual(national.loc[0, "rain_shipments"], 19.0)
        self.assertAlmostEqual(national.loc[0, "rain_volume_mt"], 91.0)
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m unittest tests.test_correlation_analysis.NationalAggregationTests -v`

Expected: FAIL with missing `build_national_panel`.

- [ ] **Step 3: Implement fixed national weighting and national correlation adapter**

```python
def build_national_panel(panel):
    shipment_totals = panel.groupby("week_start", as_index=False)[
        ["shipments", "volume_mt"]
    ].sum()
    rainfall = panel.pivot(
        index="week_start", columns="region_group", values="rain_mm_day"
    ).sort_index()
    weights = {}
    for metric in ["shipments", "volume_mt"]:
        metric_weights = panel.groupby("region_group")[metric].sum()
        metric_weights = metric_weights.reindex(rainfall.columns, fill_value=0)
        metric_weights = metric_weights / metric_weights.sum()
        weights[metric] = metric_weights.to_dict()
        shipment_totals[f"rain_{metric}"] = (
            rainfall.mul(metric_weights, axis=1).sum(axis=1).to_numpy()
        )
    return shipment_totals, weights
```

```python
def calculate_national_lag_correlations(national, max_lag=4):
    out = national.copy()
    out["iso_week"] = out["week_start"].dt.isocalendar().week.astype(int)
    rows = []
    for metric in ["shipments", "volume_mt"]:
        rain_column = f"rain_{metric}"
        for column in [rain_column, metric]:
            baseline = out.groupby("iso_week")[column].transform("mean")
            out[f"{column}_anomaly"] = out[column] - baseline
        for lag in range(max_lag + 1):
            rows.append({
                "scope": "Philippines weighted",
                "metric": metric,
                "rain_leads_weeks": lag,
                "pearson_raw": correlation(out[rain_column], out[metric].shift(-lag)),
                "spearman_raw": correlation(
                    out[rain_column], out[metric].shift(-lag), rank=True
                ),
                "pearson_anomaly": correlation(
                    out[f"{rain_column}_anomaly"],
                    out[f"{metric}_anomaly"].shift(-lag),
                ),
                "weeks": len(out) - lag,
                "active_weeks": int((out[metric] > 0).sum()),
            })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run the complete unit suite**

Run: `python3 -m unittest tests.test_correlation_analysis tests.test_forecast -v`

Expected: all tests pass.

- [ ] **Step 5: Commit national aggregation**

```bash
git add correlation_analysis.py tests/test_correlation_analysis.py
git commit -m "feat: add fixed-weight national correlation"
```

### Task 5: CLI, exports, and real-data verification

**Files:**
- Modify: `correlation_analysis.py`
- Modify: `tests/test_correlation_analysis.py`
- Modify: `.gitignore`
- Modify: `README.md`

- [ ] **Step 1: Write a failing export test**

```python
from pathlib import Path
from tempfile import TemporaryDirectory


class ExportTests(unittest.TestCase):
    def test_export_results_writes_all_analysis_tables(self):
        tables = {
            "weekly_lags": pd.DataFrame({"scope": ["A"]}),
            "monthly": pd.DataFrame({"scope": ["A"]}),
            "coverage": pd.DataFrame({"region_group": ["A"]}),
        }
        with TemporaryDirectory() as directory:
            ca.export_results(tables, Path(directory))
            self.assertEqual(
                {path.name for path in Path(directory).glob("*.csv")},
                {
                    "weekly_lag_correlations.csv",
                    "monthly_correlations.csv",
                    "coverage.csv",
                },
            )
```

- [ ] **Step 2: Run the export test and confirm it fails**

Run: `python3 -m unittest tests.test_correlation_analysis.ExportTests -v`

Expected: FAIL with missing `export_results`.

- [ ] **Step 3: Implement export and CLI orchestration**

```python
def export_results(tables, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    filenames = {
        "weekly_lags": "weekly_lag_correlations.csv",
        "monthly": "monthly_correlations.csv",
        "coverage": "coverage.csv",
    }
    for key, filename in filenames.items():
        tables[key].to_csv(output_dir / filename, index=False)
```

```python
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shipments-file", type=Path, required=True)
    parser.add_argument("--sheet", default="Raw_Cleaned")
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--rain-cache", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("correlation_output"))
    return parser.parse_args()


def complete_monday_weeks(start_year, end_year):
    start = pd.Timestamp(start_year, 1, 1)
    first_monday = start + pd.Timedelta(days=(-start.weekday()) % 7)
    final_day = pd.Timestamp(end_year, 12, 31)
    last_monday = final_day - pd.Timedelta(days=final_day.weekday())
    if last_monday + pd.Timedelta(days=6) > final_day:
        last_monday -= pd.Timedelta(days=7)
    return pd.date_range(first_monday, last_monday, freq="W-MON")


def load_rainfall(args):
    if args.rain_cache and args.rain_cache.exists():
        return pd.read_pickle(args.rain_cache)
    return rain.load_historical_data_cached(
        f"{args.start_year}-01-01", f"{args.end_year}-12-31",
        cache_version=f"correlation-{args.start_year}-{args.end_year}",
    )


def main():
    args = parse_args()
    weeks = complete_monday_weeks(args.start_year, args.end_year)
    shipments = pd.read_excel(args.shipments_file, sheet_name=args.sheet)
    port_region_map = {name: item["region_group"] for name, item in rain.PORTS.items()}
    shipments = map_shipment_regions(shipments, port_region_map)
    shipment_weekly = build_shipment_weekly_panel(
        shipments, list(rain.REGION_ORDER), weeks
    )
    rainfall = load_rainfall(args)
    rain_weekly = build_rain_weekly_panel(rainfall, weeks)
    panel = add_weekly_anomalies(
        shipment_weekly.merge(
            rain_weekly, on=["region_group", "week_start"],
            how="left", validate="one_to_one"
        )
    )
    if panel["rain_mm_day"].isna().any():
        raise ValueError("Rainfall coverage is incomplete for one or more region-weeks")
    regional = calculate_lag_correlations(panel)
    national, weights = build_national_panel(panel)
    weekly_lags = pd.concat(
        [regional, calculate_national_lag_correlations(national)], ignore_index=True
    )
    coverage = panel.groupby("region_group", as_index=False).agg(
        weeks=("week_start", "nunique"),
        min_rain_days=("rain_days", "min"),
        min_ports=("min_ports", "min"),
    )
    export_results({
        "weekly_lags": weekly_lags,
        "monthly": calculate_monthly_correlations(panel),
        "coverage": coverage,
    }, args.output_dir)
    strongest = weekly_lags.loc[
        weekly_lags.groupby(["scope", "metric"])["pearson_anomaly"].idxmin()
    ]
    print(strongest.to_string(index=False))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add repository hygiene and usage documentation**

Add to `.gitignore`:

```gitignore
__pycache__/
*.py[cod]
correlation_output/
correlation_cache/
```

Add to `README.md`:

```markdown
## Rainfall-shipment correlation

Run the five-year analysis against the shipment workbook:

python3 correlation_analysis.py \
  --shipments-file ../菲律宾镍矿装运量完成.xlsx \
  --start-year 2021 \
  --end-year 2025 \
  --output-dir correlation_output

The output separately compares rainfall with shipment count and rainfall with shipment volume. Regional de-seasonalized weekly lag correlations are the primary interpretation; raw, monthly, Spearman, and national fixed-weight tables are robustness views. Correlation does not establish causation.
```

- [ ] **Step 5: Run the full test suite**

Run: `python3 -m unittest discover -s tests -v`

Expected: all correlation and rainfall tests pass with zero failures.

- [ ] **Step 6: Run the real five-year analysis**

Run:

```bash
python3 correlation_analysis.py \
  --shipments-file ../菲律宾镍矿装运量完成.xlsx \
  --start-year 2021 \
  --end-year 2025 \
  --output-dir correlation_output
```

Expected: 30 rainfall ports, 6 regions, 260 complete weeks, no unmapped shipment ports, four CSV outputs, and separate summaries for `shipments` and `volume_mt`.

- [ ] **Step 7: Verify the result invariants**

Run:

```bash
python3 -c "import pandas as pd; d=pd.read_csv('correlation_output/weekly_lag_correlations.csv'); assert set(d.metric)=={'shipments','volume_mt'}; assert set(d.rain_leads_weeks)==set(range(5)); assert d.weeks.min()>=256; print(d.shape)"
```

Expected: assertions pass and a non-empty table shape is printed.

- [ ] **Step 8: Commit the completed analysis**

```bash
git add correlation_analysis.py tests/test_correlation_analysis.py .gitignore README.md
git commit -m "feat: add rainfall shipment correlation analysis"
```

### Task 6: Final verification and interpretation report

**Files:**
- No source changes expected.

- [ ] **Step 1: Re-run all tests from a clean command**

Run: `python3 -m unittest discover -s tests -v`

Expected: zero failures and zero errors.

- [ ] **Step 2: Re-run the real-data command using the local rainfall cache if available**

Run the Task 5 command, adding `--rain-cache correlation_cache/rain_2021_2025.pkl` when the validated cache exists.

Expected: output CSVs are regenerated and coverage remains 30 ports, 6 regions, and 260 weeks.

- [ ] **Step 3: Review the strongest-lag table manually**

Confirm that positive `rain_leads_weeks` means rainfall occurs first, that shipment-count rows never use volume rainfall weights, and that volume rows never use count rainfall weights.

- [ ] **Step 4: Report results with interpretation boundaries**

Report regional raw, regional anomaly, national weighted, monthly, Spearman, and lag findings. Explicitly distinguish seasonal association from de-seasonalized association and do not describe correlation as causation.
