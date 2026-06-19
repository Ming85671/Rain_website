# Detailed Monthly Correlation Design

## Objective

Give the monthly correlation view the same detailed analytical content as the weekly view, while preserving the different time units.

## Page structure

Add `Detailed monthly analysis` after the rolling 24-month chart and before the rolling 52-week chart. Keep the existing `Detailed weekly analysis` section unchanged below the weekly rolling chart.

Both detailed sections will contain the same two-column structure:

- left: lag profile for the selected region and metric;
- right: regional lag-correlation heatmap for the selected metric.

The existing `Region` and `Metric` selectors will control both monthly and weekly sections. All visible content remains in English.

## Monthly statistical definition

Aggregate the complete weekly panel into calendar months using the existing monthly rules:

- regional rainfall is the mean weekly `rain_mm_day` within each month;
- shipment count and shipment volume are summed within each month;
- month-of-year anomalies remove the normal seasonal pattern separately for rainfall and each shipment metric.

For lags 0 through 4, compare rainfall in month `t` with the selected shipment metric in month `t + lag`. Positive lags therefore mean rainfall occurs before the compared shipment month.

For every region, metric, and lag, publish:

- Raw Pearson correlation;
- Raw Spearman correlation;
- de-seasonalized Pearson correlation;
- valid paired-month count;
- analysis start and end dates.

The `Philippines weighted` monthly results will use the existing metric-specific weighted national rainfall series.

## Charts

The monthly lag profile will contain the same three series as the weekly lag profile: `De-seasonalized Pearson`, `Raw Pearson`, and `Raw Spearman`. Its x-axis will read `Rain leads shipments (months)` and display integer lags 0 through 4.

The monthly heatmap will use the same regional order and selected de-seasonalized Pearson coefficient as the weekly heatmap. Columns will be labeled `0m` through `4m`.

Titles will explicitly say `Monthly` or `Weekly` so the two sections cannot be confused.

## Data flow and fallback

Add a dedicated monthly-lag output table to the calculation pipeline, live result tuple, committed fallback snapshot, and page-data resolver. A missing or invalid live monthly-lag table will use the existing verified-fallback behavior.

## Testing and verification

Automated tests will verify exact calendar-month lag alignment, all three coefficients, both metrics, regional and weighted-national results, exported and loaded schemas, dynamic selector filtering, monthly axis labels, monthly heatmap labels, and preservation of weekly charts.

Rendered verification will confirm placement, English titles, selector synchronization, and the matching two-column monthly and weekly layouts before the implementation is pushed.
