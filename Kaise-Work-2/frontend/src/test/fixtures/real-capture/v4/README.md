# v4 real-capture fixtures (observed HTTP responses)

Verbatim HTTP responses captured **2026-11-14** from the live FastAPI backend
(`:8002`) after loading the demo dataset (`POST /api/datasets/demo`; 11,701
rows). These pin the **v4 wire shapes** (docs/contracts.md §5.2.2–§5.2.5) —
they are the type source for `frontend/src/lib/api.ts` (M11 lesson: type from
captures, not from docs alone). Observed data, not synthetic.

- `days_to_full.json` — `GET /api/days-to-full` 200, §5.2.3 **v2**:
  `method: "fill_at_emptying_rate"`, `target_pct: 90`,
  `stats_by_material` (brown/green/white), per-series
  `last_emptying_date` / `median_interval_days` / `predicted_full_date` /
  `is_lower_bound`, reasons `not_enough_records | zero_interval_only |
  no_numeric_fill | zero_rate`, `lower_bound_share_pct` in stats.
- `comparison.json` — `GET /api/comparison` 200, §5.2.2 **v4**: 4-scenario
  array with `naive_fixed_frequency` FIRST (355,474 m / 60 served /
  5924.6 m per stop), then `naive_sweep_all` (454,623 m), `naive_sweep_selected`
  (527,021 m), `ortools` (median 70,175 m, deterministic identical ×5);
  gains −72,398 / +456,846 / +384,448 m; `fleet_budget` demo_truck ×99 →
  49,500 EUR/day / 9,900,000 EUR/year; `observed_service_anchor`
  (26.9 % full-or-overfull, basis `observed_emptying_records`) beside cost.
- `scenarios.json` — `POST /api/scenarios` 200 (defaults), §5.2.4:
  `fixed_frequency` (852 truck-days, 426,000 EUR, overflow 2.4 %) vs
  `demand_driven` (1,040 truck-days, 520,000 EUR, overflow 0.0 %,
  max fill 80.0) — demand_driven costs MORE (honest tradeoff shown in UI);
  `observed_anchor` 26.9 %, `config_echo`, 35 `skipped_series`.
- `simulation.json` — `POST /api/simulation` 200 (defaults), §5.2.5:
  daily replay 2025-10-17 → 2026-09-30 (349 days), `data_basis`
  {records: observed, rates: derived, plan: simulated}, per-strategy
  `days[]` (date, collections, overflow_containers, truck_days,
  cumulative_cost_eur), `calibration` (simulated median 42.5 vs observed 60.0),
  `config_echo`.
- `config.json` — `GET /api/config` 200, **v4**: routing defaults now include
  `containers_per_series: 1` and `frequency_days: 28`; per-field `sources`
  plus verbatim `source_labels` (incl. the [literature] density citation).

Wording note (contracts §1.5/§5.2.2, v4): every row is an **emptying record**
(DE "Leerungsdaten") — human-visible strings flip accordingly; JSON field
names keep the historical `readings` tokens.
