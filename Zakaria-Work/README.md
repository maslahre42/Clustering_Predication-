# Smart Waste Routing — Zakaria's notebook and Gurobi pipeline

Glass-collection analysis, behavioral grouping, reset-aware demand prediction and a compact Gurobi route model for the PreZero / Fillinq challenge. The original exploratory notebook sequence and mathematical approach are retained. The correction removes invented overflow percentages and fixes the interpretation of pre-emptying visits.

Read the [method and corrections](docs/corrections-and-method.md) and [verification evidence](docs/verification.md). The original contributor review describes the **pre-correction** implementation and is not the current method specification.

## Run the corrected example

Python 3.12 is verified. From `Zakaria-Work/`:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_pipeline.py --planning-date 2026-08-17 --max-sites 24 --evaluate
```

Gurobi requires a usable license. Small demonstration models may fit an installed restricted license; a full model may require a larger license. Use Gurobi's normal license setup for your installation. The code does not change license environment variables or pretend that a license failure is a feasible plan.

The explicit `--max-sites 24` is a demonstration subset. All other selected sites are exported as deferred. Omit it to request the full selection; the solver reports insufficient fleet, license limits or time limits explicitly. Adjust `--max-vehicles` and `--time-limit` for your problem. This engine makes one collection tour per vehicle, with final unloading and return to the yard.

For analysis and forecasts without Gurobi:

```sh
python run_pipeline.py --planning-date 2026-08-17 --no-route --evaluate
```

`--csv PATH` accepts another validated reading file and `--output PATH` selects an artifact directory. The default output is `data/corrected/`. Without `--planning-date`, planning defaults to the day after the final recorded observation. `--days-ahead N` projects an uncollected future scenario; default zero estimates the dispatch day. `--fixed-travel-min 0` switches from fixed travel minutes to illustrative distance/speed time.

## Notebook guide

Open the notebooks from this directory or its parent. Each numbered notebook reconstructs its inputs through the shared loader so an old CSV cannot silently introduce another cutoff or outdated semantics. Change `PLANNING_DATE` consistently when comparing stages.

| Notebook | Purpose |
| --- | --- |
| [main.ipynb](main.ipynb) | Original exploratory narrative, corrected material/history/calendar charts and grouping |
| [01 — EDA](01_eda_and_analysis.ipynb) | Validation, glass-stream comparisons and actual visit-state audit |
| [02 — groups](02_container_clustering.ipynb) | Per-bin cutoff-safe profiles, up to four descriptive K-Means groups, sparse-history labels |
| [03 — prediction](03_fill_prediction.ipynb) | Completed-cycle median rates, common dispatch date, volume/mass and explained selection |
| [04 — Gurobi](04_gurobi_route_optimization.ipynb) | Explicit demo subset, fleet-first CVRP, route/failure outputs and Folium map |

Saved notebook outputs were cleared when the assumptions changed. Execute cells to produce current results. The raw CSV and municipal coordinate references were preserved. CSVs directly under `data/` are legacy exports; the corrected notebooks do not read them.

## Business rules

- A bin is `(Location_id, material_type)`; different colors at one location share one physical stop.
- A reading is before emptying. Each visit resets the bin; differences between visit readings do not measure continuous accumulation or detect emptyings.
- `overfull` is a category, not 110%. Numerical means exclude it. Full/overfull cycle observations provide lower bounds for the rate baseline.
- Morning dispatch uses only observations strictly before the planning day. Inclusive historical review is separate.
- A bin's cycle-rate median falls back to available same-material cycles only when needed. Otherwise its forecast stays unknown.
- Prediction starts at zero after the last emptying: median rate × elapsed days, capped at nominal 100%. This simple baseline is not a calibrated probability model.
- Default selection is predicted fill at least 80%, plus bins at least 60% at an already selected site. Every bin receives a selected/skipped explanation.
- Volume/mass, per-bin service, final unloading and return travel enter the route model. Loads and hours are recomputed before export.
- Every supplied solver site is required. There is no silent demand clipping or dropping; infeasible plans return unserved reasons. Demo-deferred sites are accounted separately.

## What was optimized

The MILP now uses `x[i,j]` rather than `x[i,j,k]`, shared load/time/order variables, tupledict adjacency sums, infeasible-arc pruning and pre-solve capacity checks. Fleet count has priority over distance. MTZ still eliminates subtours, including zero-demand cases.

For the verified 24-site / 12-vehicle example, the model has **600 binary arc variables** rather than the old formulation's **7,200**. This is a measured model-size reduction, not a claim that every dataset solves twelve times faster. See the verification report for actual runtime and solver termination.

## Artifacts and result meaning

The CLI writes cleaned readings, profiles, predictions, per-bin decisions, full selected sites, demo-deferred sites, routes, solver-unserved sites and a Folium HTML proposal. `--evaluate` adds rolling chronological metrics and cases. `manifest.json` records the source hash, cutoff, configuration, current artifact list, solver status and reconciliation counts. Only artifacts listed in that manifest belong to that run.

`route_proposal.html` labels synthetic site assignments and straight lines. Provider coordinates remain stable across subsets. Kilometers are haversine × detour, not road navigation. An uploaded coordinate table needs a verified UUID-to-site mapping before calling assignments real. The bundled official-map reference list does not supply that mapping.

Open the [verified example route map](data/corrected/route_proposal.html), [run manifest](data/corrected/manifest.json) or [forecast comparison](data/corrected/forecast_metrics.csv) to inspect the generated example.

The defaults use 3 m³ containers and 12 t payload from project mentor notes; density 350 kg/m³, truck volume 18 m³, depot/disposal points and unloading time remain assumptions. Fixed ten-minute travel is an explicit mode. Mid-route unloads, independent color chambers, equipment access constraints and time windows remain future extensions. No real-world savings or global city-wide optimality is claimed.

## Tests

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
python verify_notebooks.py --output /tmp/zakaria-executed-notebooks
```

Tests cover source validation, overflow categories, reset-aware rates, future-data invariance, sparse-history behavior, physical grouping, stable geography, failure accounting, payload/shift feasibility, zero-demand subtours, chronological evaluation and a small exhaustive route benchmark. Gurobi tests explicitly skip when its package/license is unavailable; that is not equivalent to a verified routing run.
