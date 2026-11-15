# Combined project verification

Historical snapshot before the street-routing upgrade. Current road geometry, compact-sector routing and public settings are documented in [street routing](architecture/street-routing.md). The fixed-time results below are archived evidence, not current route predictions.

Verified locally on 14 November 2026. See [implemented behavior and limitations](combined-project-integration.md) and [source attribution](../forecast_service/integrations/README.md).

## Executed checks

| Check | Result |
| --- | --- |
| API/domain/request-binding tests, including all three uploaded-data endpoints | 205 passed |
| AppHost/Docker publication configuration tests | 6 passed |
| Frontend/domain/component/tooling tests | 118 passed |
| Python worker, integration and Omar regression tests | 29 passed |
| **Total** | **358 passed, no skipped tests** |
| Nuxt type checking and production build | Passed |
| .NET solution build and API publish | Passed |
| Published Python worker with packaged contributor modules | Three simulation policies, three forecast references and Gurobi check executed |
| SQLite integrity | Source file matches the original Git blob byte for byte |
| Docker image | Not built or run; publication configuration and source inclusion checked |

Python regressions exercise strict multi-error CSV rejection, duplicate handling, dataset isolation, unknown resets, overfull-only sparse groups, reset-aware rates, cutoff/future invariance, identical held-out targets, lower-bound scoring, fixed-travel/capacity/service assumptions, missing solver status, closed-day historical service, empty collection metrics and unknown-material fallback.

Existing pandas/SWIG deprecation warnings and the Aspire CLI-bundle build warning remain; these checks passed.

## Real-data browser check

Playwright used the Nuxt app at http://127.0.0.1:3002 and .NET API at http://127.0.0.1:5081. These are local running processes, not a hosted deployment.

The browser verified:

1. Cutoff **2026-08-14**, proposal for **2026-08-17**, actual `omar-python` engine.
2. Operating-setting application and a rendered per-container forecast band.
3. Behavioral grouping/data-quality results from the same historical snapshot.
4. Three routed policies for **2026-08-10–2026-08-12**, seed **7**, one-second routing attempts.
5. Real-reading forecast comparison and an actual successful Gurobi check.
6. Proposal acceptance and CSV export retaining **107 bins, 3 trucks, 8 loads** and the correct plan date/cutoff.
7. Invalid CSV upload returning HTTP 400 and visible row/rule errors, without silently repairing rows.
8. Valid CSV upload used consistently by POST proposal, per-container forecast and three-policy simulation, with no original-inventory bins mixed in.
9. Uploaded-data manifest acceptance disabled with an explanation; switching back restores the original analysis dataset.
10. No browser page errors.

Artifacts remain under `/tmp/greencity-qa/`: `combined-browser.log`, `combined-forecast.png`, `combined-simulation.png`, `combined-manifest.png`, `combined-upload.png`. Screenshots inside the application's scrolling workspace capture the visible viewport; the browser also asserted the lower comparison/validation sections in the DOM.

## Matched real-reading forecast results

Training ended **2026-08-09**. The inspected three-day window contained **172 targets**, with **143 common uncensored numeric cases** and **29 common lower-bound cases**. All three models covered all 172 targets.

| Forecast | MAE on common numeric cases (pp) | Bias (pp) | Lower-bound shortfall (pp) |
| --- | ---: | ---: | ---: |
| Omar seasonal cycle model | 15.14 | +8.94 | 23.86 |
| Zakaria frozen cycle median | 16.48 | +6.00 | 29.00 |
| Kaise persistence reference | 21.82 | +3.08 | 31.03 |

This short sample is evidence that the connected comparison executes under a common scoring contract, not a general ranking. Numeric 100 and overfull are excluded from MAE rather than treated as exact uncensored occupancy.

## Routed simulation example

The same evaluation used **1,336 pre-start known bins** and shared applied operating settings:

| Simulated outcome | Historical calendar | Omar policy | Zakaria median policy |
| --- | ---: | ---: | ---: |
| Served site visits | 58 | 44 | 102 |
| Bins emptied | 172 | 113 | 188 |
| Truck-days | 5 | 4 | 7 |
| Working time | 29h 25m | 21h 10m | 40h 30m |
| Mean collection fill | 58.2% | 80.5% | 83.6% |
| Collections below 40% | 36.6% | 14.2% | 8.0% |
| Container-days full | 372 | 305 | 217 |
| Full-cycle events | 222 | 221 | 218 |
| Missed mandatory stop-days | 0 | 0 | 0 |

Zakaria's policy trades more work for fewer modeled full-container days in this example. The simulator shares Omar's model family; the figures are not measured savings, independent counterfactual truth or a guarantee of actual collected loads. Time-limited routing can vary between runs.

## Independent optimization example

The Gurobi check returned **optimal**, serving all **six sampled sites** in **two one-load trucks**, matching the sample's capacity lower bound of two. Fixed-minute travel did not report kilometers. This verifies the bounded one-load problem only; it does not prove the full multi-load city plan optimal.
