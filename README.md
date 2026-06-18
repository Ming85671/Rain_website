# Philippine rain

Streamlit dashboard for Philippine nickel ore loading area rainfall.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run rain.py
```

## Streamlit Cloud

Set **Main file path** to:

```text
rain.py
```

## Data source

Open-Meteo API.

## Dashboard

- Historical monthly regional rainfall
- Future 7 days regional rainfall

## Rainfall-shipment correlation analysis

Run the five-year analysis from this directory:

```bash
python3 correlation_analysis.py \
  --shipments-file ../菲律宾镍矿装运量完成.xlsx \
  --sheet Raw_Cleaned \
  --start-year 2021 \
  --end-year 2025 \
  --output-dir correlation_output
```

To run without network access, add a previously prepared and validated daily
rainfall pickle with `--rain-cache correlation_cache/rain_2021_2025.pkl`. The
command reads the cache but does not create or update one automatically.

The primary result is the regional de-seasonalized weekly lag correlation:
positive `rain_leads_weeks` means rainfall occurred that many exact calendar
weeks before the shipment measure. Shipment count and shipment volume are
analyzed separately. Raw weekly Pearson, weekly Spearman, monthly, and fixed-
weight national results are robustness checks. The exported fixed regional
weights make the national aggregation auditable.

Correlation describes association, not causation.

The command writes:

- `weekly_lag_correlations.csv`
- `monthly_correlations.csv`
- `coverage.csv`
- `regional_weights.csv`
