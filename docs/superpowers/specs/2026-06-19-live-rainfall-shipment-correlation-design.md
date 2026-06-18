# Live Rainfall-Shipment Correlation Design

## Objective

Replace the correlation page's fixed 2021-2025 snapshot with a live calculation that updates when Philippine nickel-ore shipment count, shipment volume, or rainfall data changes. Preserve the committed snapshot as a safe fallback.

## Selected architecture

The Rain Streamlit app will calculate correlation results at runtime from two authoritative sources:

- shipment records from the same MySQL `axs` table used by `Ming85671/data-analysis`;
- daily rainfall from the existing Open-Meteo loading path in `rain.py`.

The Rain deployment will use the same Streamlit `[database]` secret as the data-analysis deployment. Database credentials will remain in Streamlit Secrets and will not be committed.

Runtime calculation is preferred over scheduled CSV commits because it updates without cross-repository automation, avoids noisy generated-data commits, and uses the database directly instead of treating another application's source code as a data API.

## Data flow

1. Query `axs` for Philippine nickel-ore records from 2021 onward, selecting `load_start_date`, `load_port`, `vsl_name`, and `voy_intake_mt`.
2. Validate dates, port mappings, vessel names, and non-negative finite volume values using the existing correlation-analysis rules.
3. Determine the conservative analysis cutoff:
   - never include the current incomplete Monday-Sunday week;
   - never extend beyond the last complete week containing the latest eligible shipment record;
   - request and validate rainfall through that cutoff.
4. Build complete regional weekly panels. A missing shipment record inside the accepted analysis window represents zero shipments; missing rainfall remains a hard validation failure.
5. Recalculate regional shipment-count and volume correlations independently for lags zero through four weeks.
6. Keep national rainfall weights fixed to the verified 2021-2025 baseline so extending the observation window does not silently redefine national rainfall exposure.
7. Render the returned tables directly. The page subtitle, coverage card, and analysis dates will use the actual calculated window instead of hard-coded `2021-2025` text.

## Refresh and caching

The live shipment query and combined correlation calculation will use a six-hour Streamlit cache TTL. Open-Meteo historical data already uses a twelve-hour cache; the correlation layer may therefore refresh shipment results more often without repeatedly downloading the complete rainfall history.

Each successful result will expose its analysis start, analysis end, and whether it is live or fallback data. Streamlit reruns after cache expiry will pick up database changes automatically.

## Failure handling

The existing committed CSV files remain the fallback dataset. If database configuration is absent, the database query fails, a shipment port is unmapped, rainfall coverage is incomplete, or live calculation validation fails, the page will:

- continue rendering the verified snapshot;
- display a visible warning that live refresh failed;
- show the snapshot's actual analysis end date;
- avoid presenting fallback data as current.

Errors shown in the UI will not expose database credentials or connection details.

## Code boundaries

- `correlation_analysis.py` will expose reusable dataframe-based orchestration and dynamic complete-week helpers. The CLI and Streamlit page will call the same tested calculation path.
- `rain.py` will own Streamlit Secrets access, the cached MySQL query, live/fallback selection, and freshness messaging.
- The chart builders and statistical definitions will remain unchanged except for receiving updated result tables.
- `requirements.txt` will add the MySQL connector already used by the data-analysis application.

## Testing

Tests will cover:

- the MySQL query contract and required source columns;
- conservative cutoff selection for current, future, and stale shipment dates;
- exclusion of incomplete weeks;
- recalculation when shipment count or volume changes;
- fixed 2021-2025 national weights while the analysis window extends;
- dynamic page date and coverage labels;
- cache-independent live/fallback selection;
- fallback behavior for missing secrets, query failure, unmapped ports, and incomplete rainfall;
- preservation of existing correlation and chart tests.

## Deployment requirement

After the code is deployed, copy the existing `data-analysis` Streamlit `[database]` secret block into the Rain app's Streamlit Cloud Secrets. Until that is configured, the page will intentionally render the verified fallback snapshot with a warning.
