# Lag Profile Title Clearance Design

## Objective

Prevent the Plotly modebar from covering the lag-profile title when the pointer enters either the monthly or weekly chart.

## Design

Keep the modebar and all download, zoom, pan, reset, and fullscreen controls. Change the shared lag-profile title from one long line to two lines:

- first line: `Monthly lag profile` or `Weekly lag profile`;
- second line: the selected shipment metric and region.

Render the second line at a smaller size and increase the chart's top margin so the title and legend each retain dedicated vertical space. Because monthly and weekly charts share `build_lag_profile_chart`, the same layout fix will apply to both without changing their data, axes, hover values, or correlation calculations.

## Verification

Automated tests will require a two-line title, smaller subtitle styling, and sufficient top margin. Rendered verification will move the pointer into both monthly and weekly charts and confirm that the visible modebar does not overlap either title at the current two-column dashboard width.
