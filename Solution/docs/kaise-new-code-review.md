# Kaise's new upload compared with his previous work

Reviewed 15 November 2026. Compared `Kaise-Work-2/` directly with `Kaise-Work/`: **27 added files, 58 modified files, none removed**, excluding environments, caches and build outputs. The new directory is an untracked upload, so this is a content comparison rather than a claim about an upstream commit history. Contributor source and the integrated application were not changed by this review.

## What changed

| Area | Previous implementation | New implementation | Relevance to our solution |
| --- | --- | --- | --- |
| Rate baseline | Last numeric fill plus median consecutive-reading change rate × horizon; persistence fallback | Median `fill at emptying / elapsed days` × median collection interval; no invented fallback | Corrects the pre-emptying semantics. Our integrated adapters already made related corrections; the new reference still needs evaluation under our common scoring contract. |
| Days to full | No dedicated module | Per-bin rate, median interval, days to target, predicted target date, censored-history flag and explicit insufficient-data reasons | Useful dispatcher explanation and container interval view. Apply cutoff restrictions and uncertainty before reusing it. |
| Truck compartments | Aggregate volume and total weight | Separate brown/green/white capacity dimensions; validated custom layouts or an explicitly assumed equal-third split; every disposal visit resets all dimensions | The highest-value missing constraint to adapt into our road/sector router. Confirm actual compartment sizes rather than importing the equal-third assumption. |
| Operational settings | Smaller set of demo inputs | Travel mode, costs per truck-day/year, frequency, containers per series, density provenance, compartment layout and shift metrics | Useful parameter provenance and scenario controls. The numerical defaults are not automatically our confirmed operating inputs. |
| Scenario simulation | Route/comparison demonstration | Fixed-frequency versus demand-driven replay, daily collection/overflow/cost series, observed service anchor and calibration summaries | Useful presentation structure; current replay is exploratory and has the limitations below. |
| Frontend | Overview, lists, forecasts, routes and configuration | Scenario sliders/timeline, days-to-full panel, today's-plan toggle, presentation mode with six slides, more API fixtures and tests | Good material for a coherent hackathon demo; adapt the interaction concepts to the Nuxt application. |
| Packaging | Existing application | CI workflow, environment example, Docker ignore rules and expanded user/methodology/review documentation | Useful handover improvements. Docker support itself already existed; its presence is not a wholly new feature. |

The new API adds `/api/days-to-full`, `/api/scenarios` and `/api/simulation` on top of the previous endpoints. It remains a baseline-driven prototype; it does not add a newly trained forecasting model.

## Independently reproduced forecast results

Read the existing shared CSV from `Omar-Work/data/glass_fill_levels.csv` in place through each version's loader. Both versions use the same date-based test split.

| Forecast | Previous MAE (pp) | New MAE (pp) | New numeric cases |
| --- | ---: | ---: | ---: |
| Persistence | 22.764 | 22.764 | 1,943 |
| Rate | 25.766 | 20.146 | 1,930 |

The rate method now skips more cases, so I also checked its common numeric subset against persistence: **1,930 cases; persistence MAE 22.751 pp versus rate MAE 20.146 pp**. The improvement remains on matched cases.

This forecast estimates fill at a typical next emptying: `rate × median interval`. It deliberately ignores the requested horizon. It should not be presented as a general prediction for any chosen future date. Its errors are also not directly comparable with our earlier Omar/Kaise/Zakaria table: that table uses another time window and excludes numeric 100 from exact-error scoring as a lower bound.

## Findings before integration

### 1. The new router still does not satisfy our street-routing requirement

`src/routing/schemas.py` supports `fixed_per_leg` and `haversine_derived`. Distances remain haversine × detour in both modes; the new simulation accepts only fixed-per-leg travel. No OSRM driving matrix, street geometry or compact truck-sector ownership was added. Keep our street/sector engine when adapting his compartment rules.

### 2. Replay rates use observations from the whole replay period

In `src/api/services.py:1498`, `_simulation_setup` calls `build_days_to_full(dataset)` on the full dataset and starts replay at the dataset's earliest date. Only the initial emptying dates are restricted to the start date. Rates and the known-container universe can therefore incorporate later observations.

Reproduction: a series with January rates of **2 pp/day** becomes **52.38 pp/day** after appending February observations. The scenario setup would use that revised rate when replaying January. This is acceptable only as a clearly described in-sample scenario, not as a historically available forecast/backtest. Freeze rate fitting and inventory strictly before the evaluation window for integration.

### 3. Infeasible simulated collections can be counted as completed

`src/collection/simulation.py:354` serves a stop when `minutes == 0`, even if capacity or shift checks fail. The replay resets due bins before packing and has no missed-service accounting. Final unloading/yard return is also absent from the simulation packing budget, although the routing engine handles those legs separately.

Reproduction using accepted configuration values: a **3,000 L container**, **10 kg payload**, **300 L truck volume** and a **one-minute shift** still produced **one completed collection, one truck-day and zero simulated overflow share**. Production integration must leave impossible pickups unserved, retain their fill, and report the missed service.

### 4. Advertised routing gains are not a matched-service comparison

The supplied `docs/demo_numbers.md` reports:

- Selected naive route: **527,021 derived meters, 38 served stops, 39,960 kg**.
- Optimized route: **70,175 derived meters, 34 served stops, 18,000 kg**.
- Both start from 458 candidates and leave more than 400 unserved.

The reported 456,846-meter difference is not evidence of equivalent-service savings. The documentation acknowledges different served sets. Per-stop or per-kg normalization does not make those sets equivalent. Re-evaluate identical required stops, loads, roads, depots and constraints before using a savings headline.

### 5. Fleet and fleet-budget figures still confuse loads with vehicles

`src/routing/fleet.py:81` recommends `max(ceil(total volume / vehicle volume), ceil(total weight / payload))`. The solver supports intermediate unloading, so this is a load-count bound, not a shift-feasible truck recommendation. It also omits compartment-specific bottlenecks and working time. Pricing that number as trucks/day can substantially overstate fleet cost. This issue is inherited from the previous work rather than newly introduced.

### 6. Exploratory grouping features retain the previous delta-rate proxy

`src/analytics/series_features.py:193` still computes `(later fill - earlier fill) / days`; `grouping.py` includes that rate feature. These files are unchanged even though forecasting now follows emptying semantics. Such visit-to-visit differences must not be interpreted as within-cycle accumulation. Our current integration already replaces that feature with reset-aware cycle rates.

## Validation performed

- Ran **331 forecasting/collection/routing tests successfully**. Ten source-data tests initially skipped because the upload lacks its private `data/raw` CSV.
- Pointed only the test helper's in-memory path at the existing shared CSV and ran those **10 tests successfully**. Total: **341 distinct Python tests verified** without copying raw data into the upload.
- Independently reproduced old/new forecast MAE and the matched-case check above.
- Executed the future-rate and infeasible-pickup counterexamples.
- Did not execute the FastAPI or frontend suites: their runtime/test dependencies are absent in the available review environment. The upload's reported 573 backend and 101 frontend tests are its own recorded evidence, not results reproduced here.

## Recommended integration order

1. Adapt per-material truck compartment validation and load-reset dimensions into our street-distance/sector router, with confirmed configurable capacities.
2. Add a container days-to-target/interval panel using cutoff-safe rates or the existing forecast model, preserving censored/unknown states and uncertainty.
3. Reuse the scenario and presentation concepts. Calculate fuel/distance-related costs from actual scheduled road kilometers and truck-days with explicit price assumptions.
4. Correct replay fitting, failed-service accounting and fleet math before taking any simulation, annual budget or routing-savings headline.

The new upload is a substantial improvement in semantics, constraints and presentation. It is a useful source of targeted additions to our application; replacing the current road engine with it would lose the street routing and compact-sector behavior the user requested.

## Adopted ideas in the integrated solution

The integrated app now takes the useful product ideas through its existing cutoff-safe forecast and street router: explicit colour compartments, operating cost arithmetic from road km and used truck shifts, model time-to-full ranges with missing-data states, saved scenario baselines with completed-service checks, and a six-slide live-data presentation. It does not import Kaise’s aerial/fixed routing, equal chamber split, optimistic packing or replay fitting. See [implementation and constraints](architecture/planning-insights.md).
