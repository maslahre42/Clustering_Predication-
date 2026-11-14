# Contributor integrations

These are selective, namespaced copies of the contributor implementations, not replacement models attributed to them. They avoid the two projects' conflicting `src` package names and travel with the published API. Original projects and notebooks remain usable separately.

| Source | Reused code | Integration adaptations |
| --- | --- | --- |
| `Kaise-Work/src/data/{loader,schema}.py` | Strict CSV rules, typed readings, complete row errors/warnings | `load_glass_fill_rows` accepts request-local CSV without a temporary file; imports use `integrations.kaise` |
| `Kaise-Work/src/analytics/{series_features,grouping}.py` | Coverage gates, seeded clustering, silhouette/cluster-size/IQR checks, pressure-tier fallback | Adapter replaces consecutive-fill-change rate with reset-aware cycle rate; failed gate evidence is retained; fewer than two numeric readings cannot enter clustering; unavailable profile medians remain null |
| `Kaise-Work/src/forecasting/{baseline,features,targets}.py` | Persistence reference and prediction-time feature/target contracts | Used on matched real-reading evaluation cases; the original change-rate baseline is deliberately not used for pre-emptying dispatch |
| `Zakaria-Work/src/{data_loader,clustering,predictor}.py` | Cycle-median profiles, material fallback, reset-aware demand forecast, site-neighbor selection | Adapter builds equivalent profile input from the common snapshot; rates stay frozen during evaluation; only actual simulated collection changes reset dates |
| `Zakaria-Work/src/{optimizer,distance_provider}.py` | Independent Gurobi one-load-per-truck MILP, status/unserved accounting, consistent geography | Optimizer accepts extra per-site service minutes; fixed-travel adapter preserves distinct site identities even at coincident/missing coordinates; no claimed kilometers in fixed-time mode |
| `Omar-Work/fillinq/` | Main seasonal forecast, risk policy, multi-load OR-Tools routing and digital twin | Imported directly in development and vendored during .NET publish, as before |

`dataset.py` and `comparison.py` are the integration adapters. The original contributor defaults are not blended: physical/fleet/calendar assumptions come from one applied settings object. Zakaria's comparison policy explicitly retains his 80% urgent / 60% same-site selection thresholds; Omar uses probability thresholds. The UI identifies these different decision policies.

CSV imports use Kaise's strict integer-fill contract, rejecting invalid and duplicate rows together. Existing SQLite unknown readings remain unknown and reset a cycle; they are reported as legacy warnings rather than invented numbers. No CSV upload overwrites SQLite. Each request revalidates its selected input, and each result carries a cutoff-bounded snapshot fingerprint.

The Gurobi check uses at most six selected sites on the first working day at/after simulation start. It is an independent bounded check, not evidence that the city-wide multi-load route is globally optimal. A missing package/license is returned as `solver_unavailable`; the other analyses remain usable. Docker installs the Python package but does not provision a commercial license.
