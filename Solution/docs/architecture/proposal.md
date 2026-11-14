# Combined Python forecasts, route proposals and simulation

The [three-project integration](../combined-project-integration.md) adds Kaise’s strict CSV validation/grouping safeguards/persistence reference and Zakaria’s median-policy simulation/Gurobi checks.

The Nuxt **Forecast, routes & simulation** module now calls Omar's actual Python package. The previous C# forecast and constructive router remain tested reference domain implementations; the public proposal path uses the Python model and OR-Tools.

## Setup and normal startup

From `Solution/`:

```sh
make setup PYTHON=python3.12
make run
```

`make setup` creates `.venv`, installs `forecast_service/requirements.txt` and pytest, then restores .NET and frontend dependencies. For an existing checkout run `make setup-python PYTHON=python3.12` once. Python 3.12 is verified. `Forecast__Python` can override the interpreter path; `Forecast__Script` can override the worker location. Relative script paths resolve against the API content root.

After changing API code, restart the API/Aspire host. Source Python is loaded afresh per calculation. The SQLite connection remains read-only; the worker receives JSON snapshots and does not open or write the source database.

## Request flow

1. ASP.NET validates dates, operations and request-specific bounds.
2. Its read-only query includes only observations dated on or before the active historical cutoff.
3. `PythonForecastEngine` starts `forecast_service/worker.py` using the configured interpreter. JSON goes over standard input/output, with no shell interpolation, shared model singleton or extra public network service.
4. The worker imports the repository's `Omar-Work/fillinq` modules. Published applications include those Python source files under `forecast_service/vendor/fillinq`.
5. It fits the model and returns JSON consumed by typed frontend contracts. Dependency errors are visible, not replaced by a fake forecast or the older C# approximation.
6. Cancellation stops the process tree. A four-minute limit bounds a calculation; interactive simulations accept at most 31 days.

## APIs

- `GET /api/proposal?asOf=...`: model, bin reasons, site demand, OR-Tools routes, unserved sites, settings and assumptions. The plan day is the next configured collection day after the inclusive cutoff.
- `GET /api/forecast?asOf=...&locationId=...&material=...&horizonDays=...`: actual eligible history, expected future fill, 10–90% model band, full probability and approximate median time to full. Horizon is 1–150 days.
- `GET /api/simulation?asOf=...&start=...&end=...&seed=...`: historical-calendar, Omar-policy and Zakaria-policy routed comparison, matched real-reading forecast evaluation and bounded independent optimization check, daily series and a selection-only risk frontier. Start/end must contain 1–31 days and end on or before `asOf`; seed is 0–1,000,000.

All accept the same optional `ProposalRequest` operating overrides, including seven collection-day flags. Numeric ranges and a nonempty collection calendar are validated before invoking Python. Endpoint tests exercise actual ASP.NET query binding and prove later observations never enter the worker snapshot.

## Forecast and operational parameters

Omar's `RateModel` fits partially pooled bin/material log rates, month effects and a BW school-vacation effect with a censored likelihood for numeric 100/overfull cycles. An unknown recorded reading still resets the bin but does not supply a model rate. A zero-day forecast now returns exactly zero fill/risk/quantiles. Future-only bins do not enter historical inventory.

The UI exposes all numeric operations: bin size, density, truck payload/volume, fleet upper bound, shift, fixed driving time or coordinate-based speed/detour, yard/disposal positions, per-bin and per-stop service, unloading, lookahead, mandatory/neighbor/optional thresholds, optional detour value, fixed vehicle cost and solver budget. Calendar flags allow any nonempty collection-week pattern. Applied values survive module navigation; changing them invalidates prior analysis results.

Month multipliers and the fitted school-vacation multiplier are visible. These are fitted associations, not causal findings. Calendar data remains Omar's BW calendar implementation; future regions/years need corresponding calendar maintenance. Model bands/probabilities are not calibrated service guarantees.

OR-Tools groups selected materials into physical sites, enforces payload and optional volume capacity, shifts, intermediate unloading and final return. Oversized/shift-impossible sites are reported rather than clipped. Failed solves retain mandatory status; drop penalties prefer higher-risk mandatory service under constraints. Reported loads are rounded conservatively upward, capacities downward. Fixed-minute mode intentionally reports no kilometers. Coordinate mode retains synthetic provenance and uses haversine × detour, not road navigation.

## Simulation meaning

The app runs Omar's actual `Twin`, `run_baseline` and `run_policy`, with corrected served-stop accounting. All three scenarios:

- use only bins known before the simulation starts;
- start with identical emptying state;
- use a common seeded filling-cycle multiplier table;
- use the same applied physical/fleet/shift settings;
- reset only bins at sites actually served by their routes;
- retain missed mandatory stop-day counts.

The twin and frozen planners are fitted strictly **before the simulation start**. Recorded future visit dates within the bounded test window define the historical schedule, not training features. Overflow duration is clipped to the evaluation window so pre-period full days are not counted as new simulation-period cost.

Results compare site visits, bins emptied, truck-days, working hours, collection fill, below-40% collections, container-days full, full-cycle events and missed mandatory service. The daily chart shows served site visits. The frontier varies mandatory risk threshold without routing/capacity limits and is labeled separately; it must not be mistaken for the routed scenario table.

Daily routed simulations cap each solver attempt at two seconds; the effective value is echoed in the response/UI. The seed controls synthetic demand, while wall-clock-limited route search can still vary. This is a model-dependent exploration, not measured historical occupancy, observed savings or independent validation of the forecast family.

## Collector handoff

Accepting a proposal retains a detached copy of its plan date, history cutoff, forecasts, operations, trucks and unloading loads. The manifest shows the correct collection date separately from history cutoff and exports the same forecast route sheet. Print preserves per-truck/load order. Conversion to an editable manual draft explicitly drops solver assignments and requires new feasibility checking; it does not relabel the date or pretend the edited draft remains validated. Changing the history cutoff clears drafts and accepted metadata.

## Packaging and verification

The API publish output includes the worker, dependency manifest and Omar's Python sources. Aspire publishing uses `apps/api/Dockerfile` with repository-root context; that image installs a Python environment alongside ASP.NET. The root `.dockerignore` excludes source databases, raw CSVs, notebooks, environments and secrets. Source SQLite is still mounted read-only by Compose. Docker image execution/deployment must be verified separately where Docker is available.

Checks include Python engine/bridge tests, .NET endpoint/rule/route tests, Vue state/component tests and browser execution of forecast → simulation → accepted manifest → downloaded CSV. `make test` and `scripts/test.sh` include the Python suite; `make test-python` runs it separately. Browser verification and measured example outcomes are recorded in `docs/forecast-integration-verification.md`.
