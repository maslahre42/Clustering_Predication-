# Demo numbers — comparison + scenario engine (v4)

v3 parameter change (2026-11-14), superseded in v4 only by the density source and the new fixed-frequency scenario: the comparison runs on the §4.6 v3 representative parameters — container_volume_litres=3000 [representative], stop_service_minutes=5 [representative], travel_time_mode=fixed_per_leg with fixed_travel_minutes=10 on every leg [representative + interpretation], cost_per_truck_day_eur=500, operating_days_per_week=5, operating_days_per_year=200 [representative] — alongside the unchanged [demo assumption] values (vehicle 12,000 L / 10,000 kg x 3; densities 0.40 kg/litre — [literature] German AVV table AVV 20 01 02 (entsorgen-versorgen.de, retrieved 2026-11-14); disposal unload 30 min, shift 480 min, geography knobs, solver budget). All numbers below supersede the v2 demo numbers, which remain recorded in docs/PROGRESS.md (M12/M13 history) only. Cost figures are [predicted] derivations, never invoiced amounts (§4.4).

Reproducing command: `python -m src.api.compare_demo` (writes `docs/demo_numbers.md`; optional overrides `--data PATH --output PATH --as-of YYYY-MM-DD --horizon N`)

Dataset: `data/raw/glass_fill_levels_anonymized_f.csv` [observed] — 11701 rows, 449 locations, 1338 series, 2025-10-17..2026-09-30. Raw file immutable (AGENTS rule 4).

Prediction: as_of 2026-09-30, horizon_days 28 [demo assumption — the brief defines no horizon; the default is the observed median reading gap], method persistence (contract §2.3).

Distance provenance for ALL scenarios: haversine_straight_line_derived — great-circle haversine x detour factor (§4.6) [demo assumption]; never "road distance" — no road network data exists [observed]. Synthetic stop coordinates derive from SHA-256 of series keys; the depot and disposal site are synthetic fixtures near Heilbronn.

Naive visiting order (both sweep scenarios): §4.7 area sweep — grid cells of SWEEP_CELL_SIZE_DEG=0.01° (~1 km [demo assumption]), row-major (lat band ascending, then lon ascending), lexicographic (location_id, material_type) within a cell [demo assumption — the data has no area field, so the order is not geographic].

## Scenario 1 — naive_fixed_frequency (§4.7 v4 status quo: series due under the fixed frequency_days cycle, area-sweep order)

| metric | value |
|---|---|
| status | incomplete |
| total distance_m | 355474 (haversine_straight_line_derived) |
| total duration_min | 1410 |
| stops visited | 60 / 637 |
| vehicles available | 3 x demo_truck [demo assumption §4.6] |
| vehicles used | 3 |
| travel_time_mode | fixed_per_leg (§4.6 v3) |
| collected volume litres | 84900 |
| collected weight kg | 33960 |
| unserved stops | 577 (each with a reason in the solution) |
| fleet recommendation | 183 x demo_truck (ceil_by_volume 183, ceil_by_weight 88) |
| distance per stop served (m) | 5924.6 |
| distance per collected kg (m) | 10.5 |
| cost EUR/day | 1,500 (3 x 500 EUR/truck-day [representative]; [predicted] derived, never invoiced — §4.3/§4.4) |
| cost EUR/year | 300,000 (x 200 operating days/year [representative]) |

Observed service anchor (§4.7 status quo): 26.9 % of emptying records full or overfull (numeric >= 100 or overfull token over all 11701 records) [observed §1.5]; max observed numeric fill: 100.0 %.

Stops with no persistence value at as_of: 4 of 637 — still visited, collect 0 L / 0 kg [demo assumption labelling; contract §2.3: no number is fabricated].

Shift overruns reported (contract §4.4): 2

## Scenario 2 — naive_sweep_all (ALL series, no policy filter, naive area-sweep order)

| metric | value |
|---|---|
| status | incomplete |
| total distance_m | 454623 (haversine_straight_line_derived) |
| total duration_min | 1420 |
| stops visited | 50 / 1338 |
| vehicles available | 3 x demo_truck [demo assumption §4.6] |
| vehicles used | 3 |
| travel_time_mode | fixed_per_leg (§4.6 v3) |
| collected volume litres | 90300 |
| collected weight kg | 36120 |
| unserved stops | 1288 (each with a reason in the solution) |
| fleet recommendation | 183 x demo_truck (ceil_by_volume 183, ceil_by_weight 88) |
| distance per stop served (m) | 9092.5 |
| distance per collected kg (m) | 12.6 |
| cost EUR/day | 1,500 (3 x 500 EUR/truck-day [representative]; [predicted] derived, never invoiced — §4.3/§4.4) |
| cost EUR/year | 300,000 (x 200 operating days/year [representative]) |

Stops with no persistence value at as_of: 4 of 1338 — still visited, collect 0 L / 0 kg [demo assumption labelling; contract §2.3: no number is fabricated].

Shift overruns reported (contract §4.4): 0

## Scenario 3 — naive_sweep_selected (policy-selected series only, same area-sweep order)

| metric | value |
|---|---|
| status | incomplete |
| total distance_m | 527021 (haversine_straight_line_derived) |
| total duration_min | 1400 |
| stops visited | 38 / 458 |
| vehicles available | 3 x demo_truck [demo assumption §4.6] |
| vehicles used | 3 |
| travel_time_mode | fixed_per_leg (§4.6 v3) |
| collected volume litres | 99900 |
| collected weight kg | 39960 |
| unserved stops | 420 (each with a reason in the solution) |
| fleet recommendation | 99 x demo_truck (ceil_by_volume 99, ceil_by_weight 48) |
| distance per stop served (m) | 13869.0 |
| distance per collected kg (m) | 13.2 |
| cost EUR/day | 1,500 (3 x 500 EUR/truck-day [representative]; [predicted] derived, never invoiced — §4.3/§4.4) |
| cost EUR/year | 300,000 (x 200 operating days/year [representative]) |

Stops with no persistence value at as_of: 0 of 458 — still visited, collect 0 L / 0 kg [demo assumption labelling; contract §2.3: no number is fabricated].

Shift overruns reported (contract §4.4): 0

## Scenario 4 — ortools (OR-Tools CVRP, `src.routing.solver.solve`)

| metric | value |
|---|---|
| status | feasible |
| total distance_m | 70175 (haversine_straight_line_derived) |
| total duration_min | 580 |
| stops visited | 34 / 458 |
| vehicles available | 3 x demo_truck [demo assumption §4.6] |
| vehicles used | 3 |
| travel_time_mode | fixed_per_leg (§4.6 v3) |
| collected volume litres | 45000 |
| collected weight kg | 18000 |
| unserved stops | 424 (each with a reason in the solution) |
| fleet recommendation | 99 x demo_truck (ceil_by_volume 99, ceil_by_weight 48) |
| distance per stop served (m) | 2064.0 |
| distance per collected kg (m) | 3.9 |
| cost EUR/day | 1,500 (3 x 500 EUR/truck-day [representative]; [predicted] derived, never invoiced — §4.3/§4.4) |
| cost EUR/year | 300,000 (x 200 operating days/year [representative]) |

Selection (policy §3, default config): 458 selected / 880 skipped — the ortools and naive_sweep_selected scenarios route only selected candidates; naive_sweep_all visits all 1338 series.

## Gains (derived, metres — contract §4.7)

- selection_gain_m (naive_sweep_all - naive_sweep_selected): -72398
- routing_gain_m (naive_sweep_selected - ortools median): 456846
- total_gain_m: 384448

Different served-stop counts across scenarios are inherent — normalise with the per-stop/per-kg metrics in the tables above; never claim like-for-like distance (§4.7).

## Fleet budget (ortools recommendation x §4.6 v3 cost rates)

- fleet_budget: 99 x demo_truck — 49,500 EUR/day (99 x 500 EUR/truck-day [representative]), 9,900,000 EUR/year (x 200 operating days/year [representative]). Covers full demand incl. unserved stops (§4.4); [predicted] derived, never invoiced amounts (§4.4).

## Optimised determinism (§4.7 repetition protocol, 5 solves)

- runs: 5
- mode: identical (min == max — deterministic solution-budget stop, §4.4)
- distance_m min / median / max: 70175 / 70175 / 70175

## Assumptions (each labelled [demo assumption])

- [demo assumption] forecast horizon_days=28 (brief defines no horizon; default is the observed median reading gap)
- [demo assumption] synthetic stop coordinates derived from SHA-256 of series keys — no real coordinates exist in the data; distances are haversine_straight_line_derived, not road distance
- [demo assumption] synthetic depot 'demo_depot' and disposal site 'demo_disposal_1' near Heilbronn
- [representative] container_volume_litres=3000
- [literature] German AVV table AVV 20 01 02 (entsorgen-versorgen.de, retrieved 2026-11-14) densities_kg_per_litre=brown=0.4, green=0.4, white=0.4 kg/litre
- [demo assumption] vehicle 'demo_truck': 12000 L / 10000 kg x 3 available
- [representative] stop_service_minutes=5, [demo assumption] disposal_service_minutes=30
- [representative] max_shift_minutes=480
- [representative] travel_time_mode=fixed_per_leg, fixed_travel_minutes=10 on every leg incl. depot/disposal [interpretation — open question]
- [representative] cost_per_truck_day_eur=500, operating_days_per_week=5, operating_days_per_year=200 (cost figures derived from them are [predicted], never invoiced amounts)
- [demo assumption] geography_seed=0, geography_spread_km=6 km (synthetic-layout sensitivity knobs; defaults reproduce the current coordinates)
- [demo assumption] solver_solution_limit=200 (primary stopping criterion, deterministic; §4.7)
- [demo assumption] containers_per_series=1 (multiplies litres collected and stop service minutes; the predicted fill % is the series aggregate and does NOT change — Q11), frequency_days=28 (fixed-collection-cycle length, §4.7/§5.2.4; real schedule unknown [open question Q10])
- [demo assumption] solver_time_limit_s=30.0 (safety cap only; fires ⇒ status timeout, run not reproducible; §4.7)
- [demo assumption] naive_fixed_frequency status quo: a series is due iff as_of - last_emptying_date >= frequency_days (no last date ⇒ due; §4.6 default 28 d); 637 of the dataset series were due at as_of — the real schedule is unknown [open question Q10]
- [demo assumption] naive visiting order is the §4.7 area sweep: grid cells of SWEEP_CELL_SIZE_DEG=0.01° (~1 km), row-major, lexicographic within a cell — the data has no area field
- [demo assumption] naive zero-fill rule: series without a persistence value at as_of are still visited and collect 0 L / 0 kg
- Optimised scenario: OR-Tools stops on a fixed solution budget (solver_solution_limit) — repeated solves that reach the budget return identical totals.distance_m (contract §4.4/§4.7). The wall-clock solver_time_limit_s is a safety cap only: a run it stops before the budget is reported with status timeout and is explicitly not reproducible. The naive simulations are fully deterministic.

## Notes

- Optimised scenario: OR-Tools stops on a fixed solution budget (solver_solution_limit) — repeated solves that reach the budget return identical totals.distance_m (contract §4.4/§4.7). The wall-clock solver_time_limit_s is a safety cap only: a run it stops before the budget is reported with status timeout and is explicitly not reproducible. The naive simulations are fully deterministic.
- Unserved stops are never silently dropped (contract §4.4); the generated solution objects carry a deterministic reason per stop.
- This section below is appended from the live API (the CLI writes only the comparison above) — after a CLI regeneration, re-add it from the same curls.

## Scenario engine (§5.2.4 — cost AND service level, always together)

Values from a live run on the same demo dataset and defaults (2026-11-14): `curl -X POST localhost:8002/api/scenarios -d '{}'`. Both strategies replay the observed window (2025-10-17..2026-09-30, 349 days) on per-series fill-at-emptying rates (§5.2.3 [predicted]), §4.6 physics with flat 10-min legs (§4.4 — visiting order cannot change duration, so no solver runs here), density 0.40 kg/litre [literature AVV 20 01 02], 500 EUR/truck-day [representative]. Deterministic.

| strategy | emptyings (stops) | truck-days | cost total [predicted] | cost/year [predicted] | overflow share (container-days) | simulated emptyings full/overfull | max fill |
|---|---|---|---|---|---|---|---|
| `fixed_frequency` (every frequency_days=28 [demo assumption — real schedule unknown, Q10]) | 15,636 | 852 | 426,000 EUR | 244,126.07 EUR | 2.4 % | 14.4 % | 366.4 % |
| `demand_driven` (predicted fill ≥ select_threshold_pct=80 [demo assumption §3.1]) | 9,993 | 1,040 | 520,000 EUR | 297,994.27 EUR | 0.0 % | 0.0 % | 80.0 % |

Observed service anchor (§4.7/§5.2.4) [observed]: 26.9 % of emptying records full or overfull (numeric ≥ 100 or the overfull token over all 11,701 records); max observed numeric fill 100.0 % — the reference both strategies are judged against.

Reading the table (§6 honesty rule — cost is never shown without its service column): `fixed_frequency` is **cheaper** (852 vs 1,040 truck-days) but serves **worse** — 2.4 % of container-days overflow (10,812 overflow container-days in the replay) and one in seven simulated emptyings at/overfull. `demand_driven` eliminates overflow entirely (max fill exactly the 80 % trigger) yet **costs MORE**: its emptyings cluster onto the same days (rate-synchronised series come due together), so peak days need more trucks despite fewer total emptyings. Neither strategy beats the anchor's 26.9 % cost-neutrally — the trade-off is the honest result.

## Simulation replay (§5.2.5) and the replay-initialisation rule

`curl -X POST localhost:8002/api/simulation -d '{}'` (same defaults): start 2025-10-17, end 2026-09-30; data basis records=observed, rates=derived, plan=simulated; totals reconcile with the scenario table above (fixed_frequency 15,636 emptyings / 852 truck-days / 426,000 EUR final cumulative cost; demand_driven 9,993 / 1,040 / 520,000 EUR).

**Replay initialisation (§5.2.5 addendum)**: each series' simulated clock starts at its **latest record ≤ `start_date`** (past-only, leakage-safe); a series with no record ≤ `start_date` starts at `start_date` with fill 0. The globally-latest record must NOT seed the clock — it lies at/near the window end and would deaden the early replay (observed before the fix: 4 dead months, status-quo cost understated ~15×); a mapped date after `start_date` is a `SimulationConfigError` — honest failure, never a silent clamp.

Model consequence [observed live run, labelled in the UI timeline]: the 1,303 series with a pre-window record all seed on the same day, so `fixed_frequency` synchronises onto ~12 "mega-days" of ~1,303 emptyings each (peak day 2025-11-14 with 1,303) — a replay artefact of the initialisation rule, not observed behaviour. Calibration echo (§5.2.5): simulated fill-at-emptying median 42.5 % vs observed 60.0 % — the rate model's sanity gap, shown in TechDetails.
