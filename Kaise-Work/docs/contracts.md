# WasteRouting.AI — shared contracts

Status legend: **[observed]** = verified in `data/raw/glass_fill_levels_anonymized_f.csv`
(see `docs/data_profile.md` for the producing commands) · **[predicted]** = model/solver
output · **[demo assumption]** = labelled synthetic value, not from data ·
**[open question]** = unresolved semantics (docs/data_profile.md §13).

This file is the authority for cross-module interfaces. Specialists must read it
before editing. Changes require architect review.

## 1. Canonical fill-level reading (src/data) — v1, agreed for M2

### 1.1 `ReadingRecord` (frozen dataclass, stdlib only)

| field | type | status | notes |
|---|---|---|---|
| `location_id` | `str` | [observed] | UUID-format strings; 449 distinct; no padding [observed] |
| `material_type` | `Literal["brown","green","white"]` | [observed] | exactly these three values exist |
| `date` | `datetime.date` | [observed] | ISO `YYYY-MM-DD`, date-only; timezone-naive [open question §13.6 — do not attach a tz] |
| `fill_level_pct` | `int \| None` | [observed] | deciles 0–100 today; `None` **iff** `is_overfull` is true |
| `is_overfull` | `bool` | [observed] | preserves the literal `"overfull"` token (1,192 rows) as a distinct state |

**Deliberate non-decisions** (blocked on host answers, schema must survive either):
- `overfull` is NOT coerced to 100 [open question §13.2/§13.3].
- Decile quantization is NOT enforced (finer upstream values would be valid).
- No capacity/volume/weight on readings — absent from source [open question §13.8].

### 1.2 Invariants (validation enforces)

- I1 key `(location_id, material_type, date)` unique [observed unique today].
- I2 raw fill value is an integer in `[0,100]` or `"overfull"`; anything else is an error.
- I3 `fill_level_pct is None` exactly when raw value was `"overfull"` (loader transform).

### 1.3 `LoadResult`

```text
LoadResult = {
  dataset: Dataset,            # Dataset.empty() if any errors, by default
  errors:   list[ValidationError],   # rule id, row number, message, offending value
  warnings: list[ValidationWarning],
}
Dataset = {
  readings: list[ReadingRecord],   # source file order preserved (no sorting)
  summary:  { n_rows, n_locations, n_series, date_min, date_max,
              rows_per_material: dict[material, int] },
}
```

Clarifications agreed at M2 review (2026-11-14):
- `row_number` is the 1-based data-row index (header excluded); `0` denotes the
  header row itself (used by R1).
- "empty dataset" means `Dataset.empty()`: zeroed summary, no readings.
- `rows_per_material` always contains all three material keys, zeros included.

### 1.4 Validation rules

| id | rule | level |
|---|---|---|
| R1 | column set/header mismatch (`utf-8-sig` read; BOM expected [observed]) | error |
| R2 | missing/empty field | error |
| R3 | `material_type` outside enum | error |
| R4 | date not strict `%Y-%m-%d` | error |
| R5 | fill value not int-in-range and not `"overfull"` (I2) | error |
| R6 | duplicate key — identical row vs conflicting value both flagged | error |
| R7 | numeric fill not a multiple of 10 | warning [observed all deciles today] |

Policy: invalid rows are reported, never silently dropped or coerced; a dataset
with errors yields `dataset=None`-style empty result plus the full error list.
Raw files are read-only.

## 2. Forecast output (src/forecasting) — v1 draft, agreed for M5

### 2.1 Target definition [grounded in data; constrained by open question §13.1]

Operational question: *what will the fill level of a series
`(location_id, material_type)` be at its next observed reading after the
prediction date?* The dataset records fill only at reading dates
[observed — median gap 28 d], so evaluation happens at observed readings.
At inference/demo time the horizon is a configurable number of days
**[demo assumption — not from brief]**; at evaluation time
`target_date` = next observed reading date [observed].

### 2.2 `ForecastRecord`

| field | type | status |
|---|---|---|
| `location_id`, `material_type` | key | [observed] |
| `as_of_date` | `date` | features may use only readings with `date <= as_of_date` (normative) |
| `target_date` | `date` | next observed reading (eval) or `as_of_date + horizon_days` (inference) |
| `predicted_fill_pct` | `float` in `[0,100]` | clipped; percent units |
| `predicted_state` | `"normal" \| "full" \| "overfull"` | `full` := numeric 100 [observed], `overfull` := token [observed]; states stay distinct (§1.1 non-decision) |
| `method` | `"persistence" \| "rate"` (M5) | more at M6 |
| `horizon_days` | `int` | days as_of → target |

### 2.3 Baselines (M5 — deterministic, no ML)

- **persistence**: numeric = last observed numeric fill ≤ as_of (if the last
  reading was `overfull`, predicted_state = `overfull` and numeric falls back
  to the last numeric fill).
- **rate**: last numeric fill + per-series median daily rate over numeric
  consecutive pairs × `horizon_days`, clipped to `[0,100]`.

### 2.4 Evaluation protocol (normative for M5/M6)

- **Chronological split only** (never random row splits): train `< 2026-05-01`,
  validation `2026-05-01..2026-07-31`, test `>= 2026-08-01`
  [protocol choice for the prototype, not a brief fact].
- Numeric metrics (MAE/RMSE in percentage points) computed **only where the
  observed truth is numeric**; rows whose truth is `overfull` are excluded from
  numeric metrics and covered by state metrics — never coerced.
- State metrics: confusion counts for `full-or-overfull` vs rest at a
  configurable threshold, default 80 % **[demo assumption]**.
- Leakage: no target reading may enter any feature; prediction-time features
  use only data available at `as_of_date`.

## 3. Collection candidates (src/collection) — v1, agreed for M7

Input is a forecast batch plus the series universe; output explains both
selected and skipped containers. Nothing is silently dropped.

The challenge brief (§3 "Define General Variables", audited 2026-11-14) names
only variable *categories*, no values — every default below is therefore
**[demo assumption]**, configurable, never a magic constant.

### 3.1 `PolicyConfig` (frozen dataclass, stdlib only)

| field | type | default | status |
|---|---|---|---|
| `select_threshold_pct` | `int` in `[0,100]` | 80 (aligned with §2.4 default) | [demo assumption] |
| `uncertainty_buffer_pct` | `int` in `[0,100]` | 0 (off) | [demo assumption] |
| `overfull_always_selected` | `bool` | `True` | [demo assumption] |

Out-of-range or non-integer values ⇒ config error before any selection.

### 3.2 Selection rule

Selected iff (`predicted_state == "overfull"` **and** `overfull_always_selected`)
or `predicted_fill_pct + uncertainty_buffer_pct >= select_threshold_pct`.

### 3.3 `select_candidates` signature

```text
select_candidates(
  universe:   Iterable[SeriesKey],            # all series (location_id, material_type)
  forecasts:  Mapping[SeriesKey, ForecastRecord],  # §2.2; batch of one as_of/target
  config:     PolicyConfig,
) -> SelectionResult
```

```text
SelectionResult = {
  as_of_date, target_date: date | None,   # from the batch; None iff empty universe
  config: PolicyConfig,                   # effective config echoed
  selected: list[Candidate],              # order: predicted_fill_pct desc, ties by key
  skipped:  list[Skip],                   # order: (location_id, material_type)
}
Candidate = { location_id, material_type, predicted_fill_pct, predicted_state,
              reason_code, detail }
Skip      = { location_id, material_type,
              predicted_fill_pct | None, predicted_state | None,
              reason_code, detail }
```

### 3.4 Invariants

- Every universe series appears exactly once in `selected ∪ skipped`.
- Series without a forecast (e.g. persistence `None`, §2.3) ⇒ `Skip` with
  `predicted_* = None`, `reason_code = "no_forecast"`.
- Forecast key not in universe, or batch with mixed `as_of_date`/`target_date`
  ⇒ error; no partial output.
- `reason_code` is a stable enum: `at_or_above_threshold`, `overfull_state`,
  `below_threshold`, `no_forecast`. `detail` is deterministic and contains the
  deciding numbers, e.g. `"predicted 92.0 >= threshold 80 + buffer 0"`.
- No volume/weight/capacity fields — absent from data (§13.8); introduced at
  M8 with labelled assumptions.
- Deterministic: same inputs + config ⇒ identical output.

Clarifications agreed at M7 review (2026-11-14):
- When both rules select, `reason_code = "overfull_state"` (the override is
  the deciding cause); with the override off, an overfull series is judged on
  its numeric fallback only — the token is never coerced.
- `as_of_date`/`target_date` are `None` **iff the forecast batch is empty**
  (dates come from the batch); a non-empty universe with an empty batch yields
  all-`no_forecast` skips with `None` dates.
- Duplicate keys in `universe` ⇒ error (defends the exactly-once invariant).

## 4. Route input/output (src/routing) — v1, agreed for M8/M9

OR-Tools only (AGENTS rule 8). The brief (§3, audited 2026-11-14) names the
variable categories but supplies **no values**: every numeric default below
lives in a separate config module, labelled per value, and is **[demo
assumption]** until the host supplies real ones.

### 4.1 Units (explicit, everywhere)

| quantity | unit | notes |
|---|---|---|
| volume | litres (`int`) | container and vehicle capacity |
| weight | kilograms (`int`) | via density × collected volume |
| distance | metres (`int`) | matrix and totals |
| time | minutes (`int`) | service, travel, shift |
| fill | percent (`float`) | from forecast (§2.2) |
| coordinates | WGS84 lat/lon (`float`) | **none in data** — synthetic demo fixtures until host supplies |
| speed | km/h (`float`) | [demo assumption] for derived travel times |
| density | kg/litre (`float`) | per material; default 0.5 uniform **[demo assumption — user-agreed 2026-11-14]**, request-overridable (§4.6) |

### 4.2 Input schemas (M8)

```text
Stop = { location_id, material_type,           # key into §3 candidates
         lat, lon,                              # [demo assumption] synthetic until host data
         container_volume_litres: int,          # [demo assumption]
         predicted_fill_pct: float,             # from forecast §2.2
         service_minutes: int }                 # [demo assumption]
Depot         = { id, name, lat, lon }          # central yard
DisposalSite  = { id, name, lat, lon, service_minutes }   # unloading; ≥1
VehicleType   = { id, name, volume_capacity_litres, weight_capacity_kg,
                  count_available }
RoutingConfig = { max_shift_minutes,            # [demo assumption] brief §3
                  densities_kg_per_litre: {material: float},   # defaults §4.6, request-overridable
                  detour_factor, avg_speed_kmh, # [demo assumption] matrix derivation
                  solver_solution_limit,        # int >= 1; primary stopping criterion (v2, §4.7)
                  solver_time_limit_s }         # safety cap only (v2, §4.7)
TravelMatrix  = { point_ids: [depot+disposal+stop ids],
                  distance_m: n×n int,
                  duration_min: n×n int,        # distance/speed unless supplied
                  provenance: "haversine_straight_line_derived" | "external" }
RoutingProblem = { depot, disposal_sites, stops, vehicle_types, travel, config }
```

Straight-line-derived matrices must keep that provenance string into all
outputs and UI labels — never presented as road distance (AGENTS rule 9).

### 4.3 Output schema (M9)

```text
RoutingSolution = {
  status: "optimal" | "feasible" | "infeasible" | "timeout",   # mapped OR-Tools
  objective_value: int | None,
  routes: list[Route],
  unserved: list[{stop_key, reason}],           # never silently dropped
  totals: { distance_m, duration_min, collected_volume_litres,
            collected_weight_kg, stops_served, stops_total },
  fleet_recommendation: { vehicle_type_id, count,
                          basis: {ceil_by_volume, ceil_by_weight} },  # brief §4
  distance_provenance,                          # echoed from TravelMatrix
}
Route = { vehicle_type_id, sequence: list[Stop|DisposalSite|Depot>,
          load_progression: [volume_litres, weight_kg after each stop],
          distance_m, duration_minutes }
```

### 4.4 Invariants

- Every input stop appears in exactly one route **or** in `unserved` with a
  reason; counts reconcile (`stops_served + len(unserved) == stops_total`).
- Volume and weight capacities hold at every load-progression point.
- Route duration ≤ `max_shift_minutes` or the violation is reported, not hidden.
- Fleet recommendation = max(⌈volume/capacity⌉, ⌈weight/capacity⌉) per vehicle
  type [protocol choice v1; document in model card].
- Deterministic given inputs, config and OR-Tools version when the solution
  limit is reached (identical `totals.distance_m`); only a fired safety-cap
  timeout reintroduces wall-clock variance (§4.7).

Protocol choices agreed at M9 review (2026-11-14):
- **No OR-Tools time dimension** (empirically: a span cap on any optional node
  that cannot fit makes the model FAIL at root propagation). Shift compliance
  is enforced post-hoc: stops whose minimum round trip exceeds the shift are
  pre-filtered into `unserved`; over-long routes are truncated deterministically
  (last disposal visit first if capacities hold, then lowest-fill stops).
- Determinism is claimed (and tested) as **same status + same invariants**,
  not bitwise route sequences — GLS under a wall-clock time limit may vary.
- `objective_value` is the recomputed total route distance in metres; the
  solver's internal objective (mixed with drop penalties) is not reported.
- A vehicle may end at the depot with load aboard (yard absorbs it)
  **[demo assumption]**; fleet recommendation covers full demand including
  unserved stops.

Protocol choices agreed 2026-11-14 (v2 determinism, user-approved):
- **Primary stopping criterion is `solver_solution_limit`** (fixed solution
  budget, no wall-clock dependence); repeated solves that reach the limit on
  the same problem must return identical `totals.distance_m`.
- `solver_time_limit_s` is a **safety cap only**: if it fires before the
  solution limit, status is `timeout` and the run is explicitly
  non-reproducible — never silently presented as deterministic.

### 4.7 Comparison baselines (M12 v2, user-approved 2026-11-14)

Gain-decomposition scenarios, all sharing the §4.6 demo physics, the §3
selection policy (where applied) and the naive simulation semantics of
`src/routing/naive.py` (capacities, nearest-disposal unload, shift rules,
fleet exhaustion, per-stop unserved reasons):

| scenario id | stops visited | order | isolates |
|---|---|---|---|
| `naive_sweep_all` | all series (no selection) | area sweep (below) | status quo |
| `naive_sweep_selected` | policy-selected only | same area sweep | — (gain reference) |
| `ortools` | policy-selected only | OR-Tools (§4.3) | routing gain |

- **Area sweep order** [demo assumption — no area field in data, observed]:
  synthetic stop coordinates bucketed into grid cells of
  `SWEEP_CELL_SIZE_DEG = 0.01°` (module constant in `src/routing/naive.py`,
  ≈ 1 km, [demo assumption]); cells visited in fixed row-major order
  (lat band ascending, then lon ascending), stops within a cell in
  lexicographic `(location_id, material_type)` order.
- **Gains** (derived, reported in metres and per-stop/per-kg):
  selection gain = `naive_sweep_all − naive_sweep_selected` distance;
  routing gain = `naive_sweep_selected − ortools` distance; total = sum.
  Different served-stop counts across scenarios are inherent — normalise
  with the per-stop/per-kg metrics, never claim like-for-like distance.
- **Repetition protocol** (optimised scenario only): solve `runs = 5`
  [demo assumption] times; report `mode: "identical"` (range 0) or
  `"median_of_runs"` with min/median/max distance; **median is the value
  used in the UI and docs**.
- Legacy `naive_fixed_order` (lexicographic) stays implemented and tested
  for continuity but is **not** part of the API scenarios array; it remains
  a docs/tests baseline only.

### 4.5 Inputs still missing (ask host on site)

Real coordinates (449 locations), depot + disposal sites, fleet specs,
container volumes, densities, service times, shift rules, road matrix or
speeds. Until then the demo runs fully labelled synthetic values.

### 4.6 Agreed demo defaults (user decision 2026-11-14) — all [demo assumption]

Live in one labelled config module (`src/routing/demo_config.py`, M8); every
value overridable **per request** (M10 API validates ranges per §3.1/§4.2 and
echoes the effective config; M11 renders an editable panel that keeps the
[demo assumption] labels visible — overrides never relabel facts).

| value | default | note |
|---|---|---|
| `container_volume_litres` | 1900 | typical glass igloo size |
| `densities_kg_per_litre` | 0.5 uniform (brown/green/white) | conservative loose-cullet demo value |
| vehicle type | `demo_truck`: 12,000 L / 10,000 kg, 3 available | one type in v1 |
| `service_minutes` (stop) | 10 | |
| disposal `service_minutes` | 30 | |
| `max_shift_minutes` | 480 | 8 h demo cap |
| `avg_speed_kmh` | 30 | urban demo speed |
| `detour_factor` | 1.4 | haversine→approx road factor; provenance stays "straight-line derived" |
| `solver_solution_limit` | 200 | v2 primary stopping criterion (deterministic; §4.7) |
| `solver_time_limit_s` | 30.0 | safety cap only (v2): fires ⇒ status `timeout`, run not reproducible |

Host-supplied values replace defaults in config only — never silent.

## 5. API (src/api) — v1, agreed for M10

FastAPI + Pydantic; handlers thin, orchestration in `src/api/services.py`
using modules from §1–§4 (no business logic in handlers). JSON snake_case.
v1 keeps **one active dataset in memory** (upload replaces it) — documented
prototype limitation, not a persistence claim.

### 5.1 Endpoints

| method | path | purpose | body → response |
|---|---|---|---|
| GET | `/health` | liveness (M0, root; also `/api/health`) | — |
| POST | `/api/datasets` | upload + validate CSV (§1) | multipart file → `DatasetSummary` + errors/warnings |
| GET | `/api/summary` | active dataset summary | — → `DatasetSummary`; 404 if none |
| GET | `/api/containers` | series with last reading | — → `list[SeriesStatus]`; 404 if none |
| GET | `/api/config` | demo defaults + labels (§3.1, §4.6) | — → `ConfigDefaults` |
| POST | `/api/forecasts` | run baselines (§2) | `ForecastRequest` → `ForecastResponse` |
| POST | `/api/candidates` | selection policy (§3) | `CandidateRequest` → `SelectionResponse` |
| POST | `/api/route` | pipeline: forecast → policy → geography → solve (§4) | `RouteRequest` → `RouteResponse` |
| GET | `/api/comparison` | scenario comparison with gain decomposition (§4.7, M12) | — → `ComparisonResponse`; 404 if no dataset |
| POST | `/api/datasets/demo` | load server-side demo CSV (path fixed server-side, never client-supplied) | — → `DatasetUploadResponse`; 404 if file absent; 422 on §1 errors (same rules as upload) |

Routers mount under the **`/api` prefix**; the Vite dev proxy forwards `/api/*`
to the backend port. `horizon_days` is optional, default **28**
[demo assumption — observed median reading gap].

### 5.2 Shapes

```text
DatasetSummary  = { n_rows, n_locations, n_series, date_min, date_max,
                    rows_per_material, n_errors, n_warnings, source_name }
SeriesStatus    = { location_id, material_type, n_readings, last_date,
                    last_fill_pct | null, last_is_overfull }
ForecastRequest = { as_of_date, horizon_days >= 1 (default 28 [demo assumption]), method: "persistence"|"rate" }
ForecastResponse= { as_of_date, target_date, method, forecasts: [§2.2 records] }
CandidateRequest= ForecastRequest + policy_config?: partial §3.1
SelectionResponse = §3.3 SelectionResult (selected/skipped, reason_code+detail, config echo)
RouteRequest    = ForecastRequest + policy_config? + routing_config?
routing_config (v1 applies to the single demo vehicle type; all optional):
  { container_volume_litres, densities_kg_per_litre: {brown, green, white},
    vehicle_volume_capacity_litres, vehicle_weight_capacity_kg,
    vehicle_count_available, stop_service_minutes, disposal_service_minutes,
    max_shift_minutes, avg_speed_kmh, detour_factor, solver_solution_limit,
    solver_time_limit_s }
ConfigDefaults  = { policy: §3.1 fields, routing: the routing_config defaults
                    above (§4.6 values), assumption_fields: [names of every
                    field that is a demo assumption] }
RouteResponse   = { selection: SelectionResponse, solution: §4.3 RoutingSolution,
                    assumptions: [label strings] }
```

### 5.2.1 Wire-format pins (JSON, agreed 2026-11-14 after an M11 typing bug)

The §4.3 names are the internal domain shapes; the API serialises as follows
(frontend types must match these, not the domain forms):

- `POST /api/datasets` returns the `DatasetSummary` fields **flat**, plus
  `errors`/`warnings` — there is **no nested `summary` key**.
- `RoutingSolution.unserved[]` is **flat** `{location_id, material_type,
  reason}` (the domain `stop_key` tuple is expanded by the API layer).
- `Route.load_progression` serialises as arrays: `[volume_litres,
  weight_kg][]`.
- Route `sequence` nodes carry a `node_type` discriminator:
  `"depot" | "disposal" | "stop"`.

### 5.2.2 New shapes (user-approved 2026-11-14, overview/demo work)

`DatasetSummary` (both `/api/summary` and upload responses) gains:

```text
FillStats = { share_readings_full_or_above_pct: float,  # 1 d.p., numeric fill >= threshold_pct
              share_readings_overfull_pct: float,       # overfull rows / n_rows (§1.1: never coerced)
              share_readings_empty_pct: float,          # numeric fill == 0
              threshold_pct: int }                      # echoed; 80 = §3.1 default [demo assumption]
```

Shares are percentages of `n_rows`; overfull rows count only in the overfull
share. These are shares of **readings**, not emptying events — the data has
no collection events [observed]; never worded as "emptyings".

```text
ComparisonScenario = { method: "naive_sweep_all" | "naive_sweep_selected" | "ortools",
                       status, distance_m, duration_min, stops_served, stops_total,
                       vehicles_available, vehicles_used,
                       collected_volume_litres, collected_weight_kg,
                       unserved_count, recommended_trucks,
                       fleet_basis: {ceil_by_volume, ceil_by_weight},
                       distance_per_stop_m | null,        # distance_m / stops_served, 1 d.p.
                       distance_per_kg_m | null }         # distance_m / collected_weight_kg, 1 d.p.
ComparisonResponse = { as_of_date, target_date, horizon_days,   # fixed CLI defaults, echoed
                       method: "persistence",
                       scenarios: [ComparisonScenario],         # §4.7 ids, fixed order
                       gains: { selection_gain_m | null,        # sweep_all − sweep_selected
                                routing_gain_m | null,          # sweep_selected − ortools (median)
                                total_gain_m | null },
                       optimised_determinism: { runs: int,
                                                mode: "identical" | "median_of_runs",
                                                distance_m_median, distance_m_min,
                                                distance_m_max },
                       distance_provenance, assumptions: [labels] }
```

- v2 (2026-11-14, user-approved) **replaces** the v1 `naive`/`optimised`
  top-level keys with the `scenarios` array + `gains` + `optimised_determinism`
  (breaking for the frontend — M11 follow-up consumes the new shape).
- Per-stop/per-kg metrics are `null` on zero denominators (e.g. fleet
  exhausted before any stop), never a fabricated 0-division value.
- The `ortools` scenario's `distance_m`/`duration_min`/per-metric values are
  the **medians across `runs` solves** (§4.7); min/max live only in
  `optimised_determinism`. Scenario ordering in the array:
  `naive_sweep_all`, `naive_sweep_selected`, `ortools`.
- `distance_provenance` is `haversine_straight_line_derived` — never
  presented as road distance.

- `/api/comparison` reuses the M12 comparison core (refactor
  `src/api/compare_demo.py` so CLI and endpoint share one function; CLI
  behaviour unchanged). Reproducibility follows §4.7: medians across `runs`
  solves; residual variance, if any, is reported in `optimised_determinism`
  and noted in `assumptions`. `distance_provenance` is
  `haversine_straight_line_derived` — never presented as road distance.
- `/api/datasets/demo` reads the demo CSV from a single server-side constant
  path; the response labels `source_name` with a `demo:` prefix so the UI can
  show it as demo data.

### 5.3 Rules

- Overrides validated by constructing `PolicyConfig`/`RoutingConfig`; invalid →
  422 with the validation message; effective config echoed in every response.
- No dataset loaded → 404; CSV with §1 errors → 422 + full error list, dataset
  not replaced.
- Synthetic geography and demo values stay labelled in responses
  (`distance_provenance`, `demo_` ids, `assumptions` array) — the frontend
  must render these labels.
- `/route` always returns selection + solution, even for infeasible/timeout
  status (unserved stops with reasons) — never a bare error.
