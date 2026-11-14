# Demo script — SmartWasteRouting (M13, v2)

Goal: a 5-minute reproducible end-to-end story on real challenge data with
every assumption visibly labelled. All numeric beats verified against a live
API run on 2026-11-14 (see `docs/demo_numbers.md` for the generating CLI).

## Setup (pre-demo, from clean checkout)

```bash
uv venv --python 3.14 && uv pip install -e ".[dev]"
npm --prefix frontend install
.venv/bin/uvicorn src.api.main:app --reload &        # :8000
npm --prefix frontend run dev &                      # http://localhost:5173 (proxies to :8000)
```

Note: the Vite dev server answers on `localhost` (IPv6); in a terminal use
`curl http://localhost:5173/health`, not `127.0.0.1` [observed 2026-11-14].

## Beats

1. **Load data** — on Overview, press **Load demo data** (server-side demo
   CSV, labelled `demo:`) or drag `data/raw/glass_fill_levels_anonymized_f.csv`
   into the upload panel. KPIs appear [observed]: 11,701 readings, 449
   locations, 1,338 series, 2025-10-17..2026-09-30; 34.5 % of readings
   at/above 80 %, 10.2 % the `overfull` token (never coerced), 0.0 % empty.
   Word these as *readings* — the data has no collection/emptying events.
2. **Before/after card (three-step comparison story)** — from
   `GET /api/comparison` [observed]: ① status-quo sweep `naive_sweep_all`
   230,865 m, 78/1,338 served; ② selection effect `naive_sweep_selected`
   262,995 m, 63/458 — **negative selection gain −32,130 m, worded honestly
   ("did not pay off")**; ③ optimised `ortools` 57,657 m, 40/458, routing
   gain +205,338 m, total +173,208 m. Point at the m-per-kg column
   (5.6 → 5.0 → 2.4) as the like-for-like view; never equate raw distances.
   Technical details: determinism `identical` ×5 (57,657 m each).
3. **Containers & forecasts** — pick as_of 2026-09-30 (horizon 28
   [demo assumption: the observed median reading gap]); persistence
   baseline; honest evaluation: test MAE 22.76 pp [predicted, chronological
   split].
4. **Candidates** — threshold 80 + overfull rule [demo assumption]; 458
   selected / 880 skipped [observed] with reason badges; tweak the threshold
   live in the config editor to show adaptivity.
5. **Route** — map with numbered stops, depot/disposal icons; status
   `feasible`, 3 routes, 40 served / 418 unserved **each with a reason**,
   57,657 m / 546 min, 47,880 L / 23,940 kg; fleet recommendation 63 ×
   `demo_truck` (basis: 63 by volume, 38 by weight) [observed]. Banner:
   "synthetic demo geography — straight-line derived distances, NOT road
   distances" (`haversine_straight_line_derived`).
6. **Honesty slide** — observed vs predicted vs [demo assumption] legend
   (`docs/contracts.md`); open host questions (`docs/data_profile.md` §13,
   contracts §4.5): real coordinates, depot/disposal sites, fleet specs,
   container volumes, densities, service times, shift rules, road data.

## Rules

- Never present straight-line-derived distances as road distances.
- Never present demo defaults (fleet, density, volumes, service times,
  shift) as facts — the config panel keeps [demo assumption] labels;
  overrides never re-label a value as fact.
- Negative gains are shown as negative (e.g. selection −32,130 m), never
  spun.
- If the solver returns infeasible/timeout, show the unserved reasons —
  that is the product working as designed. A fired wall-clock safety cap
  means status `timeout` and the run is explicitly not reproducible.
- Unserved stops are never silently dropped.

## Fallback

- If upload fails: **Load demo data** (same server-side CSV, labelled).
- If a live solve is slow: the fixed solution budget (200 [demo
  assumption]) stops the solver deterministically; the 30 s wall-clock cap
  is a safety net that would show as an honest `timeout`.
