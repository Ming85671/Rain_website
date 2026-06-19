# Simplified Monthly Correlation Trend Design

## Objective

Make the rainfall-shipment correlation page answer one business question clearly:

> Are wetter months associated with lower Philippine nickel-ore shipment volume, and is that negative relationship weakening over time?

All visible page content will be in English.

## Metric decision

The primary metric will be monthly shipment volume in metric tonnes. The primary coefficient will be raw Pearson correlation because it directly measures the user's stated relationship between total monthly rainfall and total monthly shipment volume, including the recurring wet-season effect.

The page will show de-seasonalized Pearson as a secondary diagnostic. This separates the overall seasonal relationship from the relationship between unusually wet months and unusually low shipment volume. Raw Spearman will not be exposed as a primary control because it adds interpretation cost without answering a separate business question on this simplified page.

## Page structure

The page will retain a region selector and default to `Philippines weighted`. It will remove the metric and analysis selectors from the main decision path.

The first row will contain:

1. An overall monthly correlation card showing the raw Pearson coefficient for shipment volume and a plain-English strength label.
2. An explanation card comparing raw monthly Pearson with de-seasonalized monthly Pearson and stating whether the observed negative relationship is mainly seasonal.

The second row will contain a full-width rolling 24-month correlation chart. Each point will calculate raw Pearson correlation from the most recent 24 complete calendar months for the selected region. The chart will include a zero reference line and plain-English guidance that movement toward zero means the negative rainfall relationship is weakening.

The existing detailed weekly lag charts and methodology will remain available below the simplified monthly summary so analytical detail is preserved without competing with the primary conclusion.

## Interpretation rules

Correlation labels will use absolute coefficient magnitude:

- below `0.20`: no clear relationship;
- `0.20` to below `0.40`: weak relationship;
- `0.40` to below `0.60`: moderate relationship;
- `0.60` and above: strong relationship.

The direction will be stated separately as negative or positive. A rolling coefficient moving toward zero will be described as a weakening relationship, not proof of a specific new causal factor. The page will explicitly say that other factors may be becoming more important and that correlation does not establish causation.

## Data flow

The existing weekly regional and national panels will be aggregated into complete calendar months:

- rainfall: monthly mean of weekly `rain_mm_day`;
- shipment volume: monthly sum of `volume_mt`;
- shipment count: retained internally for existing detailed views.

Rolling results will require 24 valid monthly pairs. The first point will appear only after 24 months are available. Live calculations and the committed fallback snapshot will use the same calculation function. A committed rolling-correlation CSV will support the fallback page when database secrets are unavailable.

## Failure handling

If fewer than 24 valid months exist for a scope, the page will state that there is insufficient history instead of drawing a misleading line. The existing live-database warning and verified-snapshot fallback behavior will remain unchanged.

## Testing

Automated tests will cover:

- 24-month rolling-window boundaries and coefficient values;
- insufficient-history behavior;
- correlation strength and direction labels;
- the simplified page's fixed metric and coefficient choices;
- English-only visible copy for the new summary;
- live and fallback propagation of rolling results;
- preservation of existing weekly correlation behavior.

Visual verification will confirm the English layout, hierarchy, chart readability, and fallback warning state in the rendered Streamlit page.
