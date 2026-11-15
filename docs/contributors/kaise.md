# Kaise — explainable forecasting and route-planning application

## Contribution and attribution

The [Kaise-Work](../../Kaise-Work/README.md) folder contains a full-stack Python/FastAPI and React/TypeScript prototype, strict data contracts, descriptive analysis, baseline forecasting, explicit collection policy, OR-Tools routing, comparison simulations, tests and container packaging.

This report uses **Kaise** as the folder's owner label. The folder is currently untracked in the enclosing repository; no matching author identity or full name is established by its Git history. Internal progress notes describe several implementation/review roles and commit IDs from an earlier development environment. Those notes are useful historical execution evidence, but do not prove that one individual wrote every part of this imported work.

## Business purpose and full workflow

The application accepts glass-reading CSVs, explains observed patterns and forecast limits, predicts a future reading using simple baselines, selects collection candidates with explicit reasons, generates a capacity-constrained route proposal and reports all unserved bins. An operator can change forecast date/horizon and demo assumptions, inspect route loads, and compare selection/routing scenarios.

The implemented chain is upload → validation → active dataset → historical features → forecast → selected/skipped explanation → synthetic geography → route solver → served/unserved accounting → fleet requirement and map. It favors traceable rules over an unvalidated machine-learning model.

## 1. Canonical data contract and upload policy

Sources: [schema](../../Kaise-Work/src/data/schema.py), [loader](../../Kaise-Work/src/data/loader.py), [profile tool](../../Kaise-Work/src/data/profile_glass_fill.py), [contracts](../../Kaise-Work/docs/contracts.md).

The immutable reading record contains location ID, brown/green/white material, a calendar date, integer numerical percentage or `None`, and an explicit overfull flag. The invariant is `fill_level_pct is None` exactly when `is_overfull` is true. Within valid loaded data there is no separate unknown/malformed reading state: bad data rejects the upload.

The canonical loader reads UTF-8 with BOM support and validates exact header order `Location_id,material_type,date,fill_level_perc`. Rules are:

| Rule | Behavior |
| --- | --- |
| R1 | Header must match the expected columns/order |
| R2 | Four fields per row; required cells nonempty |
| R3 | Material exactly in the three-color enum |
| R4 | Strict zero-padded ISO date |
| R5 | ASCII integer 0–100, or exact literal `overfull` |
| R6 | Any repeated location/material/date key is an error, including identical duplicates |
| R7 | Numeric values not divisible by ten are accepted with a warning |

Every validation error invalidates the complete dataset; it returns an empty canonical result and the complete error list, rather than dropping or coercing bad rows. Row numbers are one-based data rows, with zero reserved for header errors. Valid source order is preserved, and summaries compute rows, distinct locations/series, date bounds and zero-filled per-material counts.

The separate profile/reporting tool audits source structure and values for reproducible data documentation. It does not rewrite raw inputs. The canonical loader and forecast schema deliberately leave the meaning of observation changes unresolved; they do not assume that a negative difference confirms an emptying.

## 2. Descriptive analysis and seasonality

Sources: [series features](../../Kaise-Work/src/analytics/series_features.py), [seasonality](../../Kaise-Work/src/analytics/seasonality.py), [holidays](../../Kaise-Work/src/analytics/holidays.py), [report](../../Kaise-Work/src/analytics/report.py), [figures](../../Kaise-Work/src/analytics/figures.py).

For each location/material series, analysis computes reading coverage, numeric/overfull counts, span, mean/median inter-reading gaps, mean numerical fill, overfull share, numerical-100 share, numerical differences and rates, and positive/negative/flat-pair counts. Only consecutive numeric/numeric pairs contribute differences; an intervening overfull token breaks the pair. Fractions use all readings as denominator where documented.

The fill-change rate is `(later_fill - earlier_fill) / gap_days`. It is explicitly a descriptive proxy, not asserted physical accumulation. Negative changes are retained. Dataset aggregates summarize those changes and irregular cadence rather than inventing regularly spaced observations.

Seasonal reports group by month, meteorological season and weekday. Winter spans December–February with the correct year boundary. Numerical means exclude overfull, while overfull shares remain explicit. Weekday counts are normalized by how often each weekday occurs in the inclusive observed date range. Statutory BW holiday inputs include Easter-derived movable dates. Holiday reporting compares readings per holiday/nonholiday day and a weekday-matched expected count, reducing simple calendar-composition confusion; it still measures collection/observation activity, not causal holiday waste generation.

The report command validates input, refuses `SYNTHETIC-` fixture IDs when real-data mode is requested, computes analysis and writes plots with units/time coverage. Spatial analysis records absent coordinates rather than claiming geographic clusters from UUIDs. The synthetic-ID prefix guard distinguishes known test fixtures; it cannot prove every other identifier belongs to a real site.

## 3. Behavioral grouping with a quality gate

Source: [grouping.py](../../Kaise-Work/src/analytics/grouping.py).

Candidate features are reading count, median gap, mean fill, overfull share, numerical-100 share and median numeric rate. K-Means eligibility requires at least three readings and all those features available. Features are standardized; zero-variance columns become zero. Seeded K-Means evaluates `k=2,3,4`, chooses highest silhouette with smaller-k tie-breaking, then accepts it only if:

- Silhouette ≥0.35.
- Every cluster has at least five series.
- Every cluster pair has nonoverlapping interquartile ranges on at least two raw features.

Otherwise the result falls back to descriptive pressure tiers. Pressure is `share_at_100 + overfull_share`: ≥0.30 high, ≥0.10 medium, otherwise low; fewer than three readings is insufficient history. These thresholds describe the dataset and are distinct from collection-policy thresholds.

All series keep labels. A nuance in the actual fallback: `tier_labels` checks reading count but does not require numerical features. An overfull-only series with at least three observations can therefore receive a high-pressure tier even though it is ineligible for K-Means. Also, on a failed gate the returned fallback object discards the attempted silhouette/gate detail; the public result does not retain all diagnostic evidence implied by the broader design description.

## 4. Prediction-time features and target definition

Sources: [features](../../Kaise-Work/src/forecasting/features.py), [targets](../../Kaise-Work/src/forecasting/targets.py).

Forecast features only use rows in the same series with `date <= as_of_date`. They include last numerical fill, whether the latest reading is overfull, days since latest reading, numerical mean/max, overfull share, count, month and median numeric-pair change/day. There is no fabricated numeric imputation for overfull-only history.

Historical evaluation asks: what will the value be at the **next observed reading**? Each consecutive pair creates a case whose prediction date is the previous observation and whose target is the next observation, with actual variable day horizon. First readings are skipped because no past case exists. A target's reading cannot enter its own feature row.

Inference uses `target_date = as_of + requested horizon`. Series first observed after the cutoff yield no forecast. The policy universe still includes all series in the uploaded dataset, so these future-only series appear as explicit `no_forecast` skips rather than disappearing. Thus features avoid future readings, although the inventory universe itself is not a strictly historical known-bin inventory.

## 5. Persistence/rate forecasts and state rules

Source: [baseline.py](../../Kaise-Work/src/forecasting/baseline.py).

```text
persistence = last numeric fill available by as_of
rate = clip(last numeric fill + median numeric-pair rate × horizon, 0, 100)
```

Without a numeric pair, rate falls back to persistence. Without any numeric history, both return no forecast. The state is overfull if the latest reading is overfull; otherwise full if predicted numerical fill reaches 100; otherwise normal. With a prior numeric observation followed by an overfull token, the forecast keeps the older numerical fallback while reporting overfull state. No number is invented for the token.

These are deterministic baselines with no fitted machine-learning estimator. Persistence does not change with horizon. The rate baseline can decrease due to negative historical changes. If visit readings are confirmed pre-emptying resets, these methods predict next-observation behavior rather than a validated physical growth trajectory after emptying.

## 6. Evaluation protocol and saved evidence

Sources: [evaluation](../../Kaise-Work/src/forecasting/evaluation.py), [report command](../../Kaise-Work/src/forecasting/report.py), [model card](../../Kaise-Work/docs/model_card.md).

Cases split chronologically by target date: before 1 May 2026 train, 1 May–31 July validation, from 1 August test. Numeric MAE/RMSE score only numeric truths with predictions; overfull truth counts and missing-numeric-history cases are reported separately. State confusion treats overfull or numerical fill ≥80 as positive by default; 80 is a configurable demo threshold, not the literal definition of full.

This is rolling historical feature evaluation: later cases can use earlier observed readings, including those in the same evaluation period. It is not a single forecast frozen before the whole test period. There is no learned model to train on the named train split in these baseline functions.

The model card records 10,363 cases over 1,338 series. Saved validation/test MAE is 27.66/22.76 pp for persistence and 30.46/25.77 for rate. It therefore leads with persistence. These numbers are existing report evidence, not rerun results. No ML model appears in `src/forecasting/`, and a trained-ML improvement must not be claimed from the stack's scikit-learn dependency alone.

## 7. Explainable collection policy

Source: [policy.py](../../Kaise-Work/src/collection/policy.py).

Defaults are an 80% selection threshold, zero uncertainty buffer and enabled overfull override. The selection condition is:

```text
(state == overfull AND overfull_always_selected)
OR predicted_fill + buffer >= threshold
```

Overfull override takes precedence as the reported reason. With it disabled, an overfull forecast is judged on its numeric fallback. Every universe series appears exactly once in selected or skipped, including no-forecast series. Selected rows sort by predicted fill descending then key; skipped rows sort by key. Duplicate universe keys, forecast keys outside the universe, mixed dates and invalid config are errors before output.

An overfull-only history has no forecast record and is skipped as `no_forecast`, even with the overfull override enabled. The override only applies to existing forecasts. The UI buffer is a deterministic margin, not a statistically estimated uncertainty interval. Some explanation text says “threshold + buffer,” while the implemented formula adds buffer to prediction; the formula above is authoritative.

## 8. Routing contracts, demo physics and geography

Sources: [schemas](../../Kaise-Work/src/routing/schemas.py), [demo defaults](../../Kaise-Work/src/routing/demo_config.py), [geography](../../Kaise-Work/src/routing/geography.py).

Routing contracts define typed depot, disposal, stops, vehicle types, matrices and config, with unit/range/key validation. Demand is rounded container liters × forecast percentage, then rounded liters × material density for kilograms. Defaults are 1,900 L/bin, 0.5 kg/L per material, three trucks each 12,000 L/10,000 kg, ten-minute stop service, thirty-minute disposal service and a 480-minute shift. These are labeled demo assumptions, not measured operational facts.

SHA-256 of the **location/material pair** deterministically generates stop coordinates around a synthetic Heilbronn depot, independent of upload ordering. Consequently colors at one location can have different demo coordinates and are separate route stops; this differs from Monir/Omar's one physical site grouping. Matrices use haversine distance ×1.4 and 30 km/h, labeled `haversine_straight_line_derived`. There is no real road service or actual UUID-to-location mapping.

## 9. OR-Tools objective, capacity and shift behavior

Source: [solver.py](../../Kaise-Work/src/routing/solver.py).

The model expands available vehicles, starts/ends at the depot, minimizes distance, and adds separate volume and weight capacity dimensions. Disposal nodes reset loads through negative transit/slack. Selected stops have a high drop penalty; unavoidable drops become unserved with reasons. Extracted capacity progressions are checked. Empty problems return zero routes and an optimal zero-distance result.

Disposal nodes are finite modeled visits, not an unrestricted repeat-unload service. The disposal disjunction call is `AddDisjunction([index])` without an explicit skip penalty. Its intended optional behavior should be checked against the installed OR-Tools API before promising freely skippable disposal visits; that library behavior was not executed in this review.

There is **no time dimension in the solver**. Shift handling happens in Python:

1. Exclude stops whose smallest individual collection round trip already exceeds the shift.
2. Solve the volume/weight/distance problem.
3. Recompute durations including service.
4. For long routes, remove the last disposal if capacity stays feasible, otherwise remove lowest-fill stops with key tie-breaking until the shift fits.
5. Return removed stops as unserved with explicit shift reasons.

Routes may return to the depot still loaded, a documented demo assumption. This differs from Omar's required final unload and Zakaria's fixed final disposal. Postprocessing does not reoptimize removed stops or prove the best shift-feasible solution.

Search uses a default 200-solution budget and 30-second safety cap. Reported status distinguishes feasible/optimal/infeasible/timeout; invalid/unusable internal status raises an error. If the safety cap fires first, the run is treated as timeout and can return every stop unserved even if an incumbent was found. Repeated determinism claims are bounded to the fixed budget and environment. Reported objective is recomputed served-route distance, excluding solver drop penalties.

Every input stop must reconcile into served routes or an unserved entry. Reasons distinguish oversized volume/weight, shift infeasibility, insufficient fleet/solver drop and overall failure. A feasible partial route set is not a guarantee that the whole candidate set is covered.

## 10. Fleet requirement

Source: [fleet.py](../../Kaise-Work/src/routing/fleet.py).

For each vehicle type:

```text
required_count = max(ceil(total_volume / vehicle_volume),
                     ceil(total_weight / vehicle_payload))
```

Demand includes served and unserved input stops; the requirement is not clamped to availability. Both ceilings are reported as basis. With multiple types, the type requiring the smallest count wins, with ID tie-breaking.

This is an aggregate single-load-equivalent capacity calculation. It omits geography, service duration, shifts and the load reduction made possible by multiple disposal trips. It is distinct from the number of routes used and is not a proven operational minimum fleet for a working day. For example, a saved run uses three actual trucks but reports a 63-truck aggregate capacity requirement.

## 11. Naive comparison and gain decomposition

Sources: [naive simulation](../../Kaise-Work/src/routing/naive.py), [comparison orchestration](../../Kaise-Work/src/api/services.py), [saved demo numbers](../../Kaise-Work/docs/demo_numbers.md).

The naive simulator sorts stops by 0.01-degree grid cells in row-major order and by location/material within cells. It unloads at the nearest disposal when the next stop would exceed capacity, hands the next stop to another vehicle when the shift is exhausted, and reports remaining bins as unserved. It also retains an older lexicographic-order mode for tests/docs. Neither is an observed historical route calendar.

Missing persistence values in the all-series comparison are still visited with labeled zero collection volume/weight. A return leg can cause naive routes to exceed the shift; these violations are reported rather than hidden. This makes the naive and adjusted optimized route feasibility conventions imperfectly matched.

Three scenarios share demo physics: sweep all series, sweep policy-selected series, and OR-Tools on selected series. Selection gain is all-sweep distance minus selected-sweep distance; routing gain is selected-sweep minus optimized; total is their sum. Five optimized runs are compared and the median-distance run supplies the reported route row, with min/median/max and repetition mode.

Saved scenario values are:

| Scenario | Served / input stops | Distance | Unserved |
| --- | ---: | ---: | ---: |
| Sweep all | 78 / 1,338 | 230,865 m | 1,260 |
| Sweep selected | 63 / 458 | 262,995 m | 395 |
| OR-Tools | 40 / 458 | 57,657 m | 418 |

Saved selection/routing/total gains are −32,130 / +205,338 / +173,208 m. The negative selection gain is preserved. Different served counts mean raw distance reductions do not establish like-for-like service savings; even distance per kg/stop cannot prove equivalent coverage or actual city savings. Synthetic coordinates, partial service and naive shift violations remain material qualifications.

## 12. FastAPI service behavior and state

Sources: [endpoints](../../Kaise-Work/src/api/endpoints.py), [services](../../Kaise-Work/src/api/services.py), [state](../../Kaise-Work/src/api/state.py), [transport schemas](../../Kaise-Work/src/api/schemas.py).

| Endpoint | Business responsibility |
| --- | --- |
| `/health`, `/api/health` | Service liveness |
| `POST /api/datasets` | Upload/validate; replace active data only on success |
| `POST /api/datasets/demo` | Load a fixed server-side CSV, friendly 404 if unavailable |
| `GET /api/summary` | Dataset coverage and fill-state counters |
| `GET /api/containers` | Latest recorded state per series |
| `GET /api/config` | Defaults and assumption labels |
| `POST /api/forecasts` | Baseline forecast batch |
| `POST /api/candidates` | Selected/skipped explanations |
| `POST /api/route` | End-to-end selection/routing with assumptions and unserved reasons |
| `GET /api/comparison` | Three fixed-default comparison scenarios |

The process holds **one shared active dataset in memory**, with upload filename and warnings. Invalid uploads return 422 and preserve the prior active dataset; endpoints needing absent data return 404. There is no per-user isolation or durable store. Restarting loses uploads, and multiple worker processes would not automatically share the same dataset.

Request overrides are validated through transport/domain contracts. Services own orchestration; thin HTTP handlers delegate. Comparisons use fixed comparison defaults rather than automatically mirroring every interactive configuration change, so users must inspect echoed dates/config before relating the two.

## 13. React interface and packaging

Sources: [App](../../Kaise-Work/frontend/src/App.tsx), [typed client](../../Kaise-Work/frontend/src/lib/api.ts), [components](../../Kaise-Work/frontend/src/components), [Dockerfile](../../Kaise-Work/Dockerfile), [SPA delivery](../../Kaise-Work/src/api/spa.py), [hosted settings](../../Kaise-Work/src/api/hosted.py).

Views cover Overview, Data, Containers, Forecast/Candidates, Routes and Config. Panels stay mounted while tabs are hidden, retaining state. Upload success increments dataset version and refreshes relevant data. Overview offers demo loading, data-derived KPIs, recommendation examples and the three-scenario story. Candidate/route views accept date, horizon, method and shared overrides; routes show maps, load progression, unserved explanations and fleet figures. Observed values, predictions and demo assumptions receive distinct labels.

English/German translation covers overview/navigation, with technical panels largely English. Each major view has a retryable error boundary. Empty/loading/error states, units, material legends and collapsible technical details support operator use. The typed client follows the actual flat wire shapes and fixture captures.

Docker packaging builds the React SPA and serves it with FastAPI through one process, honors the platform port, and excludes raw data from the image. SPA fallback preserves API/health priority and rejects traversal. A private demo CSV can be mounted separately. These files prepare deployment; they do not prove a hosted instance is currently deployed.

`WASTECITY_SOLVER_TIME_LIMIT_S` changes the fallback solver safety budget unless explicitly overridden by request. `WASTECITY_MAX_STOPS` restricts only interactive routing to the first N selected candidates; remaining candidates receive `hosted_demo_stop_cap` reasons and totals still reconcile. Comparison bypasses this cap to keep its full selection basis. Invalid environment values are logged/ignored.

A cap nuance: the solver computes fleet requirement on the capped subset, and response merging restores omitted stops/counts without recomputing that requirement. Under a cap, it should not be read as a complete-demand fleet requirement despite the normal uncapped contract.

## 14. Existing tests and delivery limits

The [backend tests](../../Kaise-Work/tests) cover strict ingestion, schema invariants, aggregate pins, holiday/grouping behavior, historical feature cutoffs, evaluation coverage, policy partitioning, routing schemas/capacities/unserved cases, fleet math, naive comparisons, API upload flows, hosted overrides and SPA delivery. [Frontend tests](../../Kaise-Work/frontend/src) exercise clients, uploads, rendering, configuration, comparison messages, route payloads, translations and errors.

The [progress log](../../Kaise-Work/docs/PROGRESS.md) records a later historical verification of 436 backend and 67 frontend tests, type/lint/build checks and Docker smoke tests. It also records real-CSV-dependent skips when private input is absent. These are imported execution claims, not fresh verification in this review. The README's older Python support table differs from the later package correction described in that log; the current [pyproject](../../Kaise-Work/pyproject.toml) should control installation requirements.

The delivered business workflow is unusually explicit about invalid data, skipped forecasts, candidate reasons, missing service and synthetic assumptions. Its main remaining limits are uncertain reading semantics, high baseline forecast error, per-material synthetic geography, partial routing coverage, shift handling after optimization, finite disposal visits, capacity-only fleet math, process-global dataset state and synthetic-comparison claims. It does not establish live occupancy forecasts, real road navigation or measured operational savings.
