# Real-capture fixtures (observed)

Verbatim HTTP responses captured **2026-11-14** from the live FastAPI backend
after loading the demo dataset (`POST /api/datasets/demo`; the same
`data/raw/glass_fill_levels_anonymized_f.csv`, 11,701 rows). These are
**observed data**, not synthetic — they pin the real wire shapes:

- `upload.json` — `POST /api/datasets` 200 (**v2-era capture**, still valid):
  **Flat** `DatasetSummary` fields + `errors`/`warnings` lists (backend
  `DatasetUploadResponse(DatasetSummaryResponse)`, contracts §5.1
  "DatasetSummary + errors/warnings"). There is **no nested `summary` key** —
  this fixture is the regression guard for the blank-page bug.
- `summary.json` — `GET /api/summary` 200 (**v2-era capture**, still valid).
- `containers.json` — `GET /api/containers` 200 (**v2-era capture**, still
  valid): all 1,338 series, including the **101 rows with
  `last_fill_pct: null` + `last_is_overfull: true`** (overfull is never
  coerced, §1.1).
- `config.json` — `GET /api/config` 200, **regenerated 2026-11-14 for v3**
  (contracts §4.6 v3/§5.2): demo defaults now include
  `vehicle_compartment_volume_litres: null` (equal thirds),
  `travel_time_mode: "fixed_per_leg"`, `fixed_travel_minutes: 10`,
  `cost_per_truck_day_eur: 500`, `operating_days_per_week: 5`,
  `operating_days_per_year: 200`, `geography_seed: 0`,
  `geography_spread_km: 6.0`, `solver_solution_limit: 200`,
  `solver_time_limit_s: 30.0`, `container_volume_litres: 3000`,
  `stop_service_minutes: 5` — plus the v3 per-field `sources` map
  (`"representative"` vs `"demo assumption"`) and the derived
  `assumption_fields`.
- `route.json` — `POST /api/route` 200 (as_of `2026-09-30`, defaults;
  **regenerated 2026-11-14 for v3**, contracts §4.3 v3/§5.2.1): feasible,
  3 routes / 34 served / **424 unserved with reasons**, totals
  70,175 m / 580 min / 45,000 L / 22,500 kg
  (`collected_volume_by_material` 15,000 L per material), fleet rec
  `demo_truck` ×99 (basis 99 by volume / 60 by weight), v3 `travel_time_mode`
  echo + `cost` block (3 vehicles in use → 1,500 EUR/day / 300,000 EUR/year;
  fleet_cost 99 trucks → 49,500 EUR/day / 9,900,000 EUR/year, all
  `[predicted]` derived), 13 assumptions. Pins the real wire shapes: FLAT
  unserved entries (`{location_id, material_type, reason}` — no `stop_key`),
  `load_progression` as `[volume_litres, weight_kg]` tuple arrays, and the
  explicit `node_type` discriminator (`stop` nodes carry `point_id`).
- `comparison.json` — `GET /api/comparison` 200 (as_of `2026-09-30`;
  **regenerated 2026-11-14 for v3**, contracts §4.7/§5.2.2): `scenarios[]` in
  the fixed §4.7 order (`naive_sweep_all` 454,623 m / 50 served / 10.1 m/kg;
  `naive_sweep_selected` 527,021 m / 38 / 10.6 m/kg; `ortools` median
  70,175 m / 34 / 3.1 m/kg), `gains` selection −72,398 / routing +456,846 /
  total +384,448, `optimised_determinism` `{runs: 5, mode: "identical"}`,
  v3 per-scenario `travel_time_mode` + cost fields (1,500 EUR/day /
  300,000 EUR/year each) and the `fleet_budget` block (`demo_truck` ×99 →
  49,500 EUR/day / 9,900,000 EUR/year). Distances are
  `haversine_straight_line_derived` — never road distance.

Earlier **v2-era** versions of `config.json`/`route.json`/`comparison.json`
(container 1,900 L, service 10 min, solver_time_limit 5 s, 63-truck fleet,
57,657 m optimised) are superseded; they remain recorded in
`docs/PROGRESS.md` (M12/M13 rows). Location IDs are anonymized challenge
identifiers; no personal data.
