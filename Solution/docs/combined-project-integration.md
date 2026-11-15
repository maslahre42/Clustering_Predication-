# Combined Python project integration

Implemented and verified on 14 November 2026. The Nuxt **Forecast, routes & simulation** workspace combines selected strengths from Omar, Kaise and Zakaria. It does not average incompatible models or present three fleet counts computed under different assumptions.

## What is connected

- **Omar:** main seasonal/censored cycle forecast, probability-based selection, multi-load OR-Tools routes, forecast curves and digital twin.
- **Kaise:** strict CSV validation with all offending rows, explicit coverage, interpretable grouping gates with pressure-tier fallback, and persistence as a real-observation reference forecast.
- **Zakaria:** corrected cycle-median forecast, same-site selection policy in the shared routed simulator, and a real bounded Gurobi optimization check.

The reused source files and integration adaptations are documented in [contributor integrations](../forecast_service/integrations/README.md). Original projects remain separate reference implementations.

## Operator workflow

1. Open **Forecast, routes & simulation** and select the historical cutoff.
2. Keep **Original SQLite observations**, or upload a readings CSV in **Analysis dataset**. Required header: `Location_id,material_type,date,fill_level_perc`. Dates must be zero-padded ISO dates, materials brown/green/white, fill an integer 0–100 or `overfull`; duplicate keys are errors. Upload limit: 2 MB.
3. Review **Data quality & behavioral groups**. If meaningful clusters fail the silhouette, minimum-size or separability gates, descriptive pressure tiers appear instead. Sparse and unknown histories remain visible.
4. Apply one set of operating assumptions. Routes, individual forecast curves and simulation use the same selected data and cutoff.
5. Choose a simulation window of 1–31 days and run it. Compare historical-calendar, Omar and Zakaria policies, then inspect the separate real-reading forecast comparison and independent optimization check.
6. Export the selected dataset's route sheet. Original-data proposals can also be accepted into the collector manifest. Uploaded datasets remain scoped to this analysis module; their routes cannot be silently applied to the unrelated original inventory.

Changing the dataset clears the collection draft and invalidates analyses. Changing dates/settings invalidates dependent results. Uploading a CSV never writes SQLite, replaces inventory in other modules, imports coordinates from unrelated UUIDs, or loads another contributor's saved metrics. CSV-only readings have no coordinates: missing positions remain unserved. Public routing now requires OSRM car streets and never invents geometry or uses fixed journey times. See [street routing](architecture/street-routing.md).

## Evaluation contract

Omar and Zakaria rate fits are frozen strictly before simulation start. Only bins already known at that point are eligible. All policies start identically, share seeded simulated demand, and use the same fleet, physical, travel, shift and working-calendar settings. Only actually served bins reset. Historical visits on a closed working day count as missed service. Historical route loads use the frozen forecast rather than future true simulated filling.

Zakaria selects bins at 80% predicted fill and additional bins at an urgent site from 60%, then uses the same Omar multi-load router. This compares decision policies without confounding them with a one-load-versus-multi-load restriction. Capacity feasibility is based on predicted loads; actual simulated filling may differ.

The separate real-reading table scores Omar, Zakaria and Kaise on identical held-out observations. Every forecast uses recorded resets strictly before its target. Rate fits remain frozen, while reset state/persistence can use intervening recorded visits. MAE and bias use the common set of uncensored numeric cases. Numeric 100 and `overfull` remain lower bounds and receive a separate shortfall score; unknown targets do not become numbers. Coverage and shared-case counts are explicit. These errors are not the simulated policy outcomes.

The digital twin shares Omar's model family and can favor that policy. A short held-out window does not establish a general model ranking or measured operational savings. Time-limited route search can vary with execution time despite a fixed demand seed.

## Independent optimization scope

Zakaria's Gurobi model runs on at most six highest-priority selected sites for the first configured collection day at/after simulation start, using the same physical settings. All sampled sites are required. Its one-load-per-truck restriction and lexicographic fleet/distance objective differ from Omar's full multi-load heuristic, so its truck count is not shown as a city-wide improvement or optimality proof.

The UI shows optimal/feasible/infeasible/unavailable status, sampled sites, capacity lower bound, truck routes, loads and working hours. A missing Gurobi package/license is explicit and does not become an empty successful route. `make setup-python` installs the package; licensing depends on the execution environment.

## API and packaging

Existing GET endpoints continue to use read-only SQLite snapshots. POST `/api/proposal`, `/api/forecast` and `/api/simulation` accept `{ "csv": "..." }` with the same date/settings query parameters. POST does not mix imported observations with SQLite or its coordinates. Validation errors return HTTP 400 with `validation.errors` and `validation.warnings`; dependency/runtime failures remain HTTP 503. The Nuxt proxy permits POST only for these analysis endpoints.

All Python source is owned inside this standalone project: `forecast_service/integrations` and `forecast_service/vendor/fillinq`. The same files travel with .NET publish and the project-local API Docker context; no sibling project folders are required. No generated environment, raw CSV, database or license is bundled in the image.

See [verification](combined-project-verification.md) for executed checks and real-data results.
