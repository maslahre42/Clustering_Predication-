# Demo numbers — naive sweep vs optimised comparison (M12 v2)

Reproducing command: `python -m src.api.compare_demo` (writes `docs/demo_numbers.md`; optional overrides `--data PATH --output PATH --as-of YYYY-MM-DD --horizon N`)

Dataset: `data/raw/glass_fill_levels_anonymized_f.csv` [observed] — 11701 rows, 449 locations, 1338 series, 2025-10-17..2026-09-30. Raw file immutable (AGENTS rule 4).

Prediction: as_of 2026-09-30, horizon_days 28 [demo assumption — the brief defines no horizon; the default is the observed median reading gap], method persistence (contract §2.3).

Distance provenance for ALL scenarios: haversine_straight_line_derived — great-circle haversine x detour factor (§4.6) [demo assumption]; never "road distance" — no road network data exists [observed]. Synthetic stop coordinates derive from SHA-256 of series keys; the depot and disposal site are synthetic fixtures near Heilbronn.

Naive visiting order (both sweep scenarios): §4.7 area sweep — grid cells of SWEEP_CELL_SIZE_DEG=0.01° (~1 km [demo assumption]), row-major (lat band ascending, then lon ascending), lexicographic (location_id, material_type) within a cell [demo assumption — the data has no area field, so the order is not geographic].

## Scenario 1 — naive_sweep_all (ALL series, no policy filter, naive area-sweep order)

| metric | value |
|---|---|
| status | incomplete |
| total distance_m | 230865 (haversine_straight_line_derived) |
| total duration_min | 1389 |
| stops visited | 78 / 1338 |
| vehicles available | 3 x demo_truck [demo assumption §4.6] |
| vehicles used | 3 |
| collected volume litres | 82270 |
| collected weight kg | 41135 |
| unserved stops | 1260 (each with a reason in the solution) |
| fleet recommendation | 116 x demo_truck (ceil_by_volume 116, ceil_by_weight 70) |
| distance per stop served (m) | 2959.8 |
| distance per collected kg (m) | 5.6 |

Stops with no persistence value at as_of: 4 of 1338 — still visited, collect 0 L / 0 kg [demo assumption labelling; contract §2.3: no number is fabricated].

Shift overruns reported (contract §4.4): 2

## Scenario 2 — naive_sweep_selected (policy-selected series only, same area-sweep order)

| metric | value |
|---|---|
| status | incomplete |
| total distance_m | 262995 (haversine_straight_line_derived) |
| total duration_min | 1364 |
| stops visited | 63 / 458 |
| vehicles available | 3 x demo_truck [demo assumption §4.6] |
| vehicles used | 3 |
| collected volume litres | 105830 |
| collected weight kg | 52915 |
| unserved stops | 395 (each with a reason in the solution) |
| fleet recommendation | 63 x demo_truck (ceil_by_volume 63, ceil_by_weight 38) |
| distance per stop served (m) | 4174.5 |
| distance per collected kg (m) | 5.0 |

Stops with no persistence value at as_of: 0 of 458 — still visited, collect 0 L / 0 kg [demo assumption labelling; contract §2.3: no number is fabricated].

Shift overruns reported (contract §4.4): 1

## Scenario 3 — ortools (OR-Tools CVRP, `src.routing.solver.solve`)

| metric | value |
|---|---|
| status | feasible |
| total distance_m | 57657 (haversine_straight_line_derived) |
| total duration_min | 546 |
| stops visited | 40 / 458 |
| vehicles available | 3 x demo_truck [demo assumption §4.6] |
| vehicles used | 3 |
| collected volume litres | 47880 |
| collected weight kg | 23940 |
| unserved stops | 418 (each with a reason in the solution) |
| fleet recommendation | 63 x demo_truck (ceil_by_volume 63, ceil_by_weight 38) |
| distance per stop served (m) | 1441.4 |
| distance per collected kg (m) | 2.4 |

Selection (policy §3, default config): 458 selected / 880 skipped — the ortools and naive_sweep_selected scenarios route only selected candidates; naive_sweep_all visits all 1338 series.

## Gains (derived, metres — contract §4.7)

- selection_gain_m (naive_sweep_all - naive_sweep_selected): -32130
- routing_gain_m (naive_sweep_selected - ortools median): 205338
- total_gain_m: 173208

Different served-stop counts across scenarios are inherent — normalise with the per-stop/per-kg metrics in the tables above; never claim like-for-like distance (§4.7).

## Optimised determinism (§4.7 repetition protocol, 5 solves)

- runs: 5
- mode: identical (min == max — deterministic solution-budget stop, §4.4)
- distance_m min / median / max: 57657 / 57657 / 57657

## Assumptions (each labelled [demo assumption])

- [demo assumption] forecast horizon_days=28 (brief defines no horizon; default is the observed median reading gap)
- [demo assumption] synthetic stop coordinates derived from SHA-256 of series keys — no real coordinates exist in the data; distances are haversine_straight_line_derived, not road distance
- [demo assumption] synthetic depot 'demo_depot' and disposal site 'demo_disposal_1' near Heilbronn
- [demo assumption] container_volume_litres=1900
- [demo assumption] densities_kg_per_litre=brown=0.5, green=0.5, white=0.5 kg/litre
- [demo assumption] vehicle 'demo_truck': 12000 L / 10000 kg x 3 available
- [demo assumption] stop_service_minutes=10, disposal_service_minutes=30
- [demo assumption] max_shift_minutes=480
- [demo assumption] avg_speed_kmh=30.0, detour_factor=1.4 (matrix derivation)
- [demo assumption] solver_solution_limit=200 (primary stopping criterion, deterministic; §4.7)
- [demo assumption] solver_time_limit_s=30.0 (safety cap only; fires ⇒ status timeout, run not reproducible; §4.7)
- [demo assumption] naive visiting order is the §4.7 area sweep: grid cells of SWEEP_CELL_SIZE_DEG=0.01° (~1 km), row-major, lexicographic within a cell — the data has no area field
- [demo assumption] naive zero-fill rule: series without a persistence value at as_of are still visited and collect 0 L / 0 kg
- Optimised scenario: OR-Tools stops on a fixed solution budget (solver_solution_limit) — repeated solves that reach the budget return identical totals.distance_m (contract §4.4/§4.7). The wall-clock solver_time_limit_s is a safety cap only: a run it stops before the budget is reported with status timeout and is explicitly not reproducible. The naive simulations are fully deterministic.

## Notes

- Optimised scenario: OR-Tools stops on a fixed solution budget (solver_solution_limit) — repeated solves that reach the budget return identical totals.distance_m (contract §4.4/§4.7). The wall-clock solver_time_limit_s is a safety cap only: a run it stops before the budget is reported with status timeout and is explicitly not reproducible. The naive simulations are fully deterministic.
- Unserved stops are never silently dropped (contract §4.4); the generated solution objects carry a deterministic reason per stop.
