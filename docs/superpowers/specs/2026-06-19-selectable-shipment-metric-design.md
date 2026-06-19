# Selectable Shipment Metric Design

## Objective

Let users compare rainfall correlation against either shipment count or shipment volume without mixing metrics across page sections.

## Controls

Add a `Metric` selector beside `Region` with two English options:

- `Shipment count`
- `Shipment volume (mt)`

`Shipment volume (mt)` remains the default so the existing primary view is preserved.

## Dynamic titles and copy

The page title will follow the selected metric:

- shipment count: `Rainfall impact on nickel ore shipments`
- shipment volume: `Rainfall impact on nickel ore volume`

The volume title intentionally does not include the word `shipment`.

All visible supporting text, card descriptions, chart labels, and explanatory copy will refer to either shipment count or shipment volume as appropriate. All visible content remains in English.

## Synchronized analysis

One selection will update every analytical section together:

- overall monthly Raw Pearson correlation;
- monthly de-seasonalized Pearson comparison;
- rolling 24-month Raw Pearson trend;
- detailed weekly lag profile;
- regional lag heatmap.

The page must never show a count headline with a volume chart, or the reverse.

## Data changes

The rolling monthly output will include a `metric` column and calculate separate 24-month trends for `shipments` and `volume_mt`. Existing monthly and weekly outputs already contain both metrics.

The committed fallback CSV and live calculation path will use the same two-metric schema.

## Testing

Automated tests will cover:

- rolling calculations for count and volume independently;
- propagation of the new `metric` column through fallback and live paths;
- metric-specific monthly summaries and descriptions;
- metric-specific chart filtering and labels;
- exact count and volume page titles;
- preservation of existing fallback behavior.

Rendered verification will switch both selector options and confirm that every visible title, card, and chart updates consistently.
