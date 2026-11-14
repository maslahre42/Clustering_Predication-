# Challenge submission and demo guide

This prototype addresses the five deliverables in the [PreZero challenge brief](../20261113_Readme%20Challenge%20PZ.docx). Use the Nuxt application as the demonstration interface. The original contributor projects remain references; the live application calls their integrated Python implementations.

## Deliverables

| Challenge deliverable | Where to demonstrate it |
| --- | --- |
| Upload and process fill-level data | **Forecast, routes & simulation → Import a different CSV**. Strict row validation, duplicate rejection, 2 MB limit, request-local data isolation. |
| Visualize patterns, groups and anomalies | **Historical analytics**: material comparisons, monthly charts, exact partial-period labels, cycle rates, distributions and historical review flags. **Forecast → Supporting details**: behavioral groups, sparse-history gates, fitted monthly and school-vacation associations. |
| Configurable operational variables | **Collection settings**: bin volume, density, truck payload/volume, fleet availability, travel, service and unloading time, depot/disposal positions, shift and working days, risk thresholds. Apply changes to recalculate. |
| Automatically propose routes and fleet | **Your collection proposal**: forecast-based bin selection, grouped stops, OR-Tools multi-load truck routes, predicted loads, working time, required fleet and explicit unserved-stop reasons. Accept into the manifest or export CSV. |
| Explain the approach | This guide, [architecture and assumptions](architecture/proposal.md), [integration and evaluation contract](combined-project-integration.md), and [setup](../README.md). |

## Five-minute demonstration

1. Start from `Solution/`: `make setup` on a fresh checkout, then `make run`. Open `http://localhost:3000`.
2. Select **2026-09-30** at the top and open **Historical analytics**. The data contains **11,701 readings, 449 locations and 1,338 observed bins**, from **2025-10-17 to 2026-09-30**. A bin is a location/material pair; a collection count is a bin emptying, not a truck trip or unique site visit.
3. Show September brown glass: **221 collections, 9 overfull, 34.2% numeric mean**. Change the date to **2026-09-08**: **9 collections, 0 overfull, 28.9%**, now explicitly marked as a partial month. Change the chart between collection count and mean fill to see the difference between frequency and fill at visits.
4. Inspect **Accumulation between emptyings** and **Containers to investigate**. Open a flagged location to inspect its recorded history. Rates assume each visit empties that bin. Full/overfull cycles are lower bounds, not exact rates; unknown visits still reset the interval. Review flags describe history rather than dispatch urgency.
5. Select **2026-08-14**, open **Forecast, routes & simulation**, review the collection settings and apply changes. The next weekday plan is **2026-08-17**. Show trucks, loads, urgent/optional stops and missed service. Reducing truck payload illustrates feasibility limits rather than silently shrinking demand.
6. Open **Data quality & behavioral groups** and **How the forecast works & assumptions** under supporting details. Explore an individual container's forecast curve. Groups use reset-aware features and fall back to descriptive tiers when cluster quality gates fail.
7. Run **2026-08-10–2026-08-12**, seed **7**, with a one-second solver attempt for a short demonstration. Compare historical-calendar, Omar and Zakaria policies. Show the separate three-model comparison against held-out real readings and the bounded Gurobi check.
8. Choose **Use as collection plan**, then **Download CSV** or **Print / save as PDF**. Truck/load assignments and the historical cutoff remain attached to the accepted plan. Changing the date clears the draft.
9. Return to the forecast module and upload a CSV. Invalid rows produce specific errors. Valid uploads drive forecasts/routes/simulation without changing SQLite or mixing original bins into the uploaded inventory. Uploaded routes can be exported directly; acceptance into the original inventory's manifest is disabled.

Example upload:

```csv
Location_id,material_type,date,fill_level_perc
demo-site,white,2026-07-01,30
demo-site,white,2026-07-11,50
demo-site,white,2026-07-21,70
demo-site,white,2026-07-31,60
```

Keep fixed travel time for uploads without coordinates. Use **Use original dataset** to return to the source inventory.

## Evidence and interpretation

Full-history median rates from **uncensored numeric cycles only** are **0.93 pp/day brown**, **2.22 green**, and **2.86 white**. They use 2,425 / 2,761 / 2,267 cycles respectively; another 233 / 960 / 1,717 full-or-overfull cycles supply lower bounds and are excluded from those medians. Comparisons are affected by collection timing and censoring. They are not network-wide live filling rates.

The transparent historical review rules flag **550 bins** at the full cutoff. At least three visits are required: either two explicit overfull readings, or at least three ≤30% readings comprising at least half the visits. The page shows up to 20, prioritizing repeated overfull. These flags are prompts to inspect scheduling; low fill alone does not prove an unnecessary collection.

The freshly executed three-day comparison has **172 held-out targets**, including **143 shared uncensored numeric cases** and **29 lower-bound cases**. MAE is **15.14 pp** for Omar, **16.48 pp** for Zakaria and **21.82 pp** for Kaise's persistence reference. This short window demonstrates a common evaluation contract rather than a general model ranking.

| Simulated measure | Historical calendar | Omar policy | Zakaria policy |
| --- | ---: | ---: | ---: |
| Served site visits | 58 | 44 | 102 |
| Bins emptied | 172 | 113 | 188 |
| Truck-days | 5 | 4 | 7 |
| Total working time | 29h 25m | 21h 10m | 40h 30m |
| Container-days full | 372 | 305 | 217 |
| Missed mandatory stop-days | 0 | 0 | 0 |

These are simulated outcomes with shared seeded demand, frozen pre-period fitting and common operating settings. They are not measured operational savings. The Gurobi check served all six sampled sites in two one-load trucks; its optimal status applies only to that bounded sample. The full city plan uses time-limited heuristic search.

## Verification and reproducibility

On 14 November 2026, **209 API + 6 AppHost + 126 frontend + 29 Python tests passed (370 total)**. Vue/TypeScript checking, the .NET solution build and the Nuxt production build passed. Aspire reports its existing CLI-bundle warning; Python reports dependency deprecations.

```sh
make test
make typecheck
make build-api
# Separate build directory permits building while the development server runs:
NUXT_BUILD_DIR=.nuxt/challenge-build make build-web
API_BASE=http://localhost:5080 python3 scripts/smoke-test.py
API_BASE=http://localhost:5080 python3 scripts/challenge-smoke.py --report /tmp/challenge-evidence.json
```

The challenge smoke check exercises real HTTP endpoints with the bundled dataset: partial/full-month regressions, forecast bounds, route accounting, payload/shift limits, three-policy simulation, held-out comparison, Gurobi availability/status, CSV rejection/isolation and impossible-load reporting. It emits a JSON evidence report when requested. Route search can produce different feasible routes across runs.

Live verification used a freshly started API on `127.0.0.1:5081` and the production Nuxt server on `127.0.0.1:3002`. Headless Edge/Playwright verified partial/full-month counts, both chart filters, a 390 px mobile layout without horizontal page overflow, review-flag navigation to history, unapplied-setting guards, a real one-day simulation and held-out comparison, plan acceptance, CSV contents, cutoff-driven draft clearing, and invalid/valid upload isolation. No browser page errors occurred. Local evidence is under `/tmp/challenge-evidence.json`, `/tmp/challenge-browser.log` and `/tmp/greencity-qa/challenge-*.png`; the downloaded route sheet is `/tmp/greencity-qa/challenge-route.csv`. SQLite's Git blob hash remained `928d4a651ab4721c051f901519196da0a1021efe`, identical to `HEAD`.

## Prototype boundaries

The brief explicitly accepts a hackathon prototype. The implemented workflow covers its deliverables. Operational deployment still requires verified site/depot mappings, calibrated weights, road travel times, and confirmed fleet details. Current routing enforces total truck payload/volume and shifts; separate color compartments and vehicle/bin compatibility remain extensions. Fixed travel mode reports time rather than fabricated kilometers. Coordinates retain their provenance.

The source covers less than one year; fitted calendar effects are associations with limited seasonal evidence. The digital twin shares Omar's model family, so independent operational validation remains necessary. Uploads and plans are temporary; there is no authentication, durable dispatch or driver completion tracking. The original notebook is exploratory and its earlier drop-based emptying or invented overflow-percentage conclusions are not used by the application.
