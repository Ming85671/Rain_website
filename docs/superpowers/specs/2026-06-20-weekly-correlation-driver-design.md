# Weekly Correlation Driver Card Design

## Goal

Explain whether the five-year weekly rainfall-shipment relationship is driven by the normal wet-season pattern or remains after weekly seasonality is removed.

## Statistical scope

- Use the selected scope and metric's lag-zero weekly row.
- Display `pearson_raw` as `Raw weekly` and `pearson_anomaly` as `After seasonality`.
- Treat the anomaly coefficient as a comparison of unusually wet weeks against unusually high or low weekly shipments after removing the normal calendar-week pattern.
- Use all complete weeks, matching the `Overall weekly correlation` card; do not use the rolling 52-week series.

## Layout and copy

- Replace the single full-width monthly driver card with two equal columns.
- Keep `What is driving the monthly relationship?` on the left.
- Add `What is driving the weekly relationship?` on the right.
- Each card contains two mini-panels and one plain-English interpretation.
- Preserve the headline cards, charts, selectors, and all unrelated styling.

## Verification

- Extend the weekly summary unit test to require the anomaly-adjusted coefficient and explanation.
- Pin the weekly driver-card labels and unusual-week copy in the page-source test.
- Run the full test suite and Streamlit page runner, then verify local and remote commit parity after push.
