# Routing methodology (M13)

How routes are produced: inputs, distance provenance, constraints, the
solver setup, unserved handling, fleet sizing, and the comparison design.
Authority: `docs/contracts.md` §4 (esp. §4.4, §4.6, §4.7) and §5; numbers
below marked [observed live run 2026-11-14] come from that session's API
run on the demo dataset (as_of 2026-09-30, horizon 28).

Status legend: **[observed]** = verified in the challenge data ·
**[predicted]** = model/solver output · **[demo assumption]** = labelled
synthetic value, not from data.

## 1. Distance provenance

There is no road-network, matrix or speed data in the challenge inputs
[observed]. Travel matrices are built from synthetic coordinates (SHA-256
derived per series key) via great-circle haversine distance × detour factor
1.4 [demo assumption] at an urban demo speed of 30 km/h [demo assumption].
Provenance is recorded as `haversine_straight_line_derived` and echoed into
every solution, comparison response and UI label. **These are never
presented as road distances.**

## 2. Demo physics (all [demo assumption], §4.6, per-request overridable)

| value | default |
|---|---|
| container volume | 1,900 L (glass igloo) |
| density | 0.5 kg/L uniform (brown/green/white) |
| vehicle | `demo_truck`: 12,000 L / 10,000 kg, 3 available |
| service time | 10 min/stop, 30 min at disposal |
| shift | 480 min |
| solver | solution_limit 200 (primary), time_limit 30 s (safety cap) |

## 3. OR-Tools setup (src/routing/solver.py)

- **Model**: CVRP with two capacity dimensions — volume (litres) and weight
  (kg, = volume × density). The disposal site visit **unloads and resets
  both dimensions**.
- **Droppable stops**: optional nodes with a large drop penalty; a dropped
  stop becomes `unserved` with a reason — never silently discarded.
- **Stopping criterion (v2)**: the fixed `solver_solution_limit` (200
  solutions). Repeated solves reaching the budget on the same problem return
  identical `totals.distance_m`. The wall-clock `solver_time_limit_s` is a
  **safety cap only**: if it fires first, status is `timeout` and the run is
  explicitly non-reproducible.
- **No time dimension** in the OR-Tools model: empirically, a span cap on
  any optional node that cannot fit makes the model FAIL at root
  propagation [observed during M9].
- Status mapping is honest: `optimal`/`feasible`/`infeasible`/`timeout`;
  NOT_SOLVED/INVALID → error. `objective_value` is the recomputed total
  route distance (metres), not the solver's penalty-mixed internal value.

Demo result [observed live run 2026-11-14]: status `feasible`, 3 routes,
57,657 m / 546 min, 40 of 458 candidates served.

## 4. Shift handling (post-hoc, §4.4)

Because the model has no time dimension, the 480-min shift [demo
assumption] is enforced **after** solving:

1. **Prefilter**: stops whose minimum round trip (depot → stop → nearest
   disposal → depot) exceeds the shift go straight to `unserved` with a
   reason.
2. **Truncation**: over-long routes are truncated deterministically —
   last disposal visit first (if capacities still hold), then lowest-fill
   stops; truncated stops become `unserved` with reasons.
3. **Reporting**: any residual route duration > shift is reported as a
   violation, never hidden.

## 5. Unserved reasons

Every input stop appears in exactly one route **or** in `unserved` with a
deterministic reason (capacities, shift, fleet exhaustion, no forecast
value, solver drop). Counts reconcile: `stops_served + unserved ==
stops_total`. Demo run [observed live run 2026-11-14]: 40 served / 418
unserved (selection: 458 selected / 880 skipped upstream).

## 6. Fleet recommendation

Per vehicle type, per the brief's "recommend fleet size from total weight
and volume":

```text
recommended_count = max(⌈total_volume_litres / volume_capacity⌉,
                        ⌈total_weight_kg / weight_capacity⌉)
```

with `basis: {ceil_by_volume, ceil_by_weight}` echoed so the driving
constraint is visible. The recommendation covers full demand including
unserved stops; the demo run gives 63 × `demo_truck` (basis 63 by volume,
38 by weight) [observed live run 2026-11-14].

## 7. Comparison design (v2, contracts §4.7)

Three scenarios isolate where improvement comes from; all share the demo
physics and the naive simulation semantics (`src/routing/naive.py`):
capacities, nearest-disposal unload, shift rules, fleet exhaustion,
per-stop unserved reasons.

| scenario | stops visited | order | isolates |
|---|---|---|---|
| `naive_sweep_all` | all 1,338 series (no selection) | area sweep | status quo |
| `naive_sweep_selected` | 458 policy-selected only | same area sweep | selection reference |
| `ortools` | 458 policy-selected only | OR-Tools | routing gain |

- **Area sweep order** [demo assumption]: the data has no area field
  [observed], so synthetic coordinates are bucketed into 0.01° grid cells
  (≈1 km), visited row-major; within a cell, lexicographic
  `(location_id, material_type)`.
- **Gains** (derived, metres): selection = sweep_all − sweep_selected;
  routing = sweep_selected − ortools; total = sum. Demo values [observed
  live run 2026-11-14]: −32,130 / +205,338 / +173,208 m. The negative
  selection gain (fewer stops under the same inefficient order) is reported
  honestly; served counts differ by design, so like-for-like judgement uses
  the per-stop/per-kg metrics (5.6 → 5.0 → 2.4 m/kg), never raw distance.
- **Repetition protocol** (optimised only): 5 solves [demo assumption];
  mode `identical` (min = max) or `median_of_runs` with min/median/max.
  The **median is the value used in the UI and docs**. Demo: identical ×5,
  57,657 m each [observed live run 2026-11-14].

Reproduce all numbers: `.venv/bin/python -m src.api.compare_demo` (writes
`docs/demo_numbers.md`) or run the app per `docs/user_guide.md` §2.
