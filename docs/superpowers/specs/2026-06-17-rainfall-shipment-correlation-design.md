# Rainfall and Philippine Nickel Ore Shipment Correlation Design

## Objective

Build a reusable analysis that measures two separate relationships:

1. regional rainfall versus shipment count;
2. regional rainfall versus shipment volume.

The analysis must not treat shipment count versus shipment volume as a reported correlation.

## Selected method

Use a region-first weekly analysis for the five complete calendar years from 2021 through 2025.

- Align rainfall and shipments to complete Monday-Sunday weeks.
- Map each loading port to the region definitions already maintained in `rain.py`.
- Calculate regional rainfall as the mean daily precipitation across the ports in that region, followed by the weekly mean.
- Calculate weekly shipment count from loading records and weekly shipment volume from `voy_intake_mt`.
- Reindex every region to a complete weekly calendar so a week with no shipment is represented as zero rather than missing.
- Report Pearson correlation as the main coefficient because rainfall and shipment magnitude are analytically meaningful.
- Report Spearman correlation as a robustness check against extreme rainfall and non-linear monotonic relationships.
- Calculate correlations for rainfall in week `t` against shipments in weeks `t` through `t+4`.
- Calculate both raw correlations and de-seasonalized correlations. De-seasonalization subtracts each region's five-year mean for the corresponding ISO week from rainfall and each shipment metric.

The primary interpretation is the de-seasonalized Pearson result. Raw Pearson describes the visible seasonal relationship but must not be presented as evidence that rainfall directly causes lower shipments.

## Regional and national results

Regional results are primary because Philippine rainfall seasons differ by region.

The national result is secondary. It uses fixed 2021-2025 regional shipment-share weights rather than a simple mean of regional rainfall. Shipment-count weights are used for the shipment-count analysis, and shipment-volume weights are used for the shipment-volume analysis. Fixed weights prevent regions with more rainfall coordinates from being overrepresented and avoid changing the rainfall definition each week.

## Port mapping and validation

The analysis imports the port-to-region map from `rain.py` so rainfall and correlation logic use one source of truth.

The shipment source currently requires one explicit alias:

- `Hinituan & Talavera Islands` -> `Hinituan&Talavera Islands`

The analysis must fail with a clear list if any shipment port cannot be mapped. It must also validate that rainfall covers all expected ports and all complete weeks.

## Code boundaries

Create a standalone analysis module and command-line entry point. The module will expose focused functions for:

- loading and validating shipment records;
- obtaining or loading cached Open-Meteo rainfall data through the existing Rain website logic;
- building regional weekly panels;
- removing weekly seasonality;
- calculating current-week and lagged correlations;
- building the fixed-weight national summary;
- exporting tidy CSV result tables.

The first implementation does not change the Streamlit page. Page integration is a separate step after the calculation and outputs are verified.

## Outputs

The command writes reproducible tables for:

- same-week regional and national correlations;
- 0-4 week lag correlations;
- raw Pearson, de-seasonalized Pearson, and Spearman coefficients;
- observation count, active-shipment weeks, date range, and coverage diagnostics.

It also prints a concise summary identifying the strongest negative lag for shipment count and shipment volume separately.

## Testing

Tests will cover:

- port alias mapping and unmapped-port failure;
- Monday-Sunday weekly alignment;
- zero-filling of no-shipment weeks;
- regional rainfall averaging without overweighting a region's port count at national level;
- de-seasonalization by region and ISO week;
- lag direction, where a positive lag means rainfall occurs before the compared shipment week;
- independent shipment-count and shipment-volume result rows;
- deterministic fixed-weight national aggregation.

## Interpretation constraints

Correlation is not causation. The output will distinguish raw seasonal correlation from de-seasonalized operational correlation. Sparse regions and the heterogeneous `Other-Check` group will be clearly identified so their coefficients are not over-interpreted.
