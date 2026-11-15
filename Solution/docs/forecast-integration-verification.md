# Omar integration verification

> This records the initial Omar-only integration. The later [three-project verification](combined-project-verification.md) supersedes its test totals and adds Kaise/Zakaria functionality.

Verified locally on 2026-11-14. The application now calls the actual `Omar-Work/fillinq` Python model, OR-Tools router and digital twin through the .NET API.

## Using the feature

Open **Forecast, routes & simulation** in the sidebar. Set the historical cutoff, review/apply operating parameters, then use the **Forecast curves** and **Simulation & backtest** links near the top of the module. Forecasts and simulations run explicitly from their buttons; they are not precomputed screenshots.

The verified development instance is http://127.0.0.1:3002 with API http://127.0.0.1:5081. These addresses require the local processes to remain running. Normal startup instructions are in [the architecture guide](architecture/proposal.md).

## Corrections

- Accepted proposals preserve the future collection date separately from the historical cutoff, plus forecasts, settings, trucks and unloading loads through manifest display and CSV export.
- Both routers prioritize higher-risk mandatory service when capacity prevents serving every site. Oversized and impossible stops remain explicit unserved demand rather than having their demand clipped.
- All numeric operating parameters and all seven calendar days are exposed, with validation and stale-result invalidation.
- Forecasting includes month and school-vacation effects, actual observation history, daily expected fill, a 10–90% model band and full probability.
- The historical-calendar and dynamic-policy simulations use pre-start training only, common simulated demand and the same physical constraints. Only actually served sites reset; missed mandatory service remains visible.
- Generated Python environments and bytecode were removed from Git tracking while retaining local files. Ignore rules prevent reintroduction. Existing Git history was not rewritten.

## Automated verification

| Suite | Passed |
| --- | ---: |
| API/domain/request-binding | 205 |
| Aspire AppHost and Docker publication configuration | 6 |
| Frontend components/state/tooling | 113 |
| Python engine adapter and Omar regressions | 17 |
| **Total** | **341** |

Nuxt type checking, the Nuxt production build, .NET build and API publish also passed. The published API contains the worker and vendored Omar source; executing that published worker returned a real six-point forecast. The SQLite source file matches its original Git content byte for byte. Container publication configuration is tested; a Docker image was not built or run.

Tests cover inclusive cutoffs, future-row exclusion, unknown-reading resets, zero-day forecasts, mandatory risk priority, impossible demand, unserved baseline accounting, settings/query binding, analysis invalidation, accepted-plan dates and route export.

## Real-browser verification

Playwright drove the actual Nuxt UI against the running .NET API and Python engine, with no browser page errors:

1. Selected history through **2026-08-14** and loaded a Python proposal for **2026-08-17**.
2. Changed and applied the solver budget through the settings form.
3. Selected a bin and rendered its daily forecast and uncertainty band.
4. Ran **2026-08-10 through 2026-08-12**, seed **7**, and rendered both routed simulation scenarios.
5. Accepted the proposal, confirmed the manifest date/cutoff, and downloaded `collection-plan-2026-08-17.csv` containing **107 bin rows, 3 trucks and 8 loads**, with forecast columns.

Temporary browser evidence is under `/tmp/greencity-qa/`: `omar-forecast.png`, `omar-simulation.png`, `omar-manifest.png` and the downloaded CSV. These files are local verification artifacts, not application source.

The inspected simulation trained through **2026-08-09**, with 1,336 known bins:

| Modeled outcome | Historical calendar | Dynamic policy |
| --- | ---: | ---: |
| Served site visits | 58 | 44 |
| Bin collections | 172 | 113 |
| Truck-days | 5 | 4 |
| Working time | 29h 25m | 21h 10m |
| Mean collection fill | 58.2% | 80.5% |
| Collections below 40% | 36.6% | 14.2% |
| Container-days full | 372 | 305 |
| Full-cycle events | 222 | 221 |
| Missed mandatory stop-days | 0 | 0 |

These are model-dependent simulation outputs, not measured savings or independent forecast validation. Time-limited route search can vary between runs. Interactive simulation windows are limited to 31 days; each daily solver attempt is capped at two seconds. The threshold frontier is selection-only and is labeled separately from routed outcomes. Fixed-time travel does not claim kilometers, and synthetic coordinates remain identified.
