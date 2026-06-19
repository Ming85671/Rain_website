# Rolling Weekly Correlation Design

## Objective

Add a weekly trend that shows how the rainfall relationship with nickel ore shipments changes through time at a finer resolution than the existing monthly trend.

## Placement and controls

Add `Rolling 52-week correlation` immediately below the existing rolling 24-month chart and above `Detailed weekly analysis`.

The existing `Region` and `Metric` selectors will control the weekly chart. Selecting shipment count or shipment volume must update the weekly line, hover text, and labels consistently.

## Statistical definition

For every complete week, calculate Raw Pearson correlation using that week and the preceding 51 complete weeks:

- rainfall and shipments are compared in the same week with no lag;
- the calculation uses 52 observations when all values are available;
- shipment count and shipment volume are calculated separately;
- regional scopes use regional rainfall and shipments;
- `Philippines weighted` uses the existing metric-specific national rainfall weighting.

The chart spans the full five-year analysis period. The first 51 weeks have insufficient history and therefore do not have correlation values; the weekly line begins at the first valid 52-week endpoint. No correlation will be fabricated for the unavailable period.

## Chart presentation

The chart will use a continuous line without visible point markers. Hovering over the line will show:

- week date;
- Raw Pearson correlation;
- selected region;
- selected metric;
- `52 complete weeks` as the calculation window.

The chart will use the same correlation scale, zero reference line, colors, and explanatory language as the monthly trend. Visible page content remains in English.

## Data flow

The analysis pipeline will produce a separate rolling-weekly table with one row per scope, metric, and valid weekly endpoint. The table will be written to the verified fallback output and returned by the live calculation path.

The page data resolver will load and validate this table alongside the existing weekly lag, monthly, and rolling-monthly outputs. A missing or invalid live rolling-weekly table will follow the existing safe fallback behavior.

## Testing and verification

Automated tests will verify:

- one 52-week Raw Pearson value per valid weekly endpoint;
- independent shipment-count and shipment-volume calculations;
- regional and weighted-national output coverage;
- stable empty output schema when fewer than 52 weeks are available;
- fallback and live loading of the new table;
- filtering by the selected region and metric;
- a line-only chart with no visible markers and complete hover information.

Rendered verification will confirm both metric options, a five-year x-axis, weekly hover details, and placement below the monthly chart.
