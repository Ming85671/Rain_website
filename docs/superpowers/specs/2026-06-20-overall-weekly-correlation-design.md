# Overall Weekly Correlation Design

## Goal

Add a clear five-year weekly counterpart to the existing overall monthly correlation so users can compare the relationship at both time resolutions.

## Statistical scope

- Use all complete Monday-Sunday weeks in the selected region and metric, not only the latest 52 weeks.
- Use the lag-zero `pearson_raw` value from `weekly_lag_correlations.csv`.
- Describe the coefficient with the same plain-English strength bands used by the monthly card.
- Keep the rolling 52-week chart unchanged; it answers how the relationship changes over time rather than the overall five-year relationship.

## Page layout

- Show `Overall monthly correlation` and `Overall weekly correlation` as two equal cards in the first row.
- Move the existing `What is driving it?` monthly-seasonality explanation into a full-width card below them.
- State that the weekly value compares rainfall and shipments in the same week across all complete weeks.
- Preserve the existing metric and region selectors, detailed charts, toolbars, and calculation outputs.

## Error handling and verification

- Raise a clear error if the selected scope and metric do not have exactly one lag-zero weekly row.
- Add unit coverage for metric selection, lag-zero selection, coefficient description, and the five-year explanatory copy.
- Run the full test suite, Python compilation, diff checks, and rendered page inspection before publishing.
