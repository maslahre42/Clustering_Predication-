# SmartWasteRouting — user guide (M13)

Explainable glass-waste collection forecasting and route-optimisation
prototype for the PreZero / City of Heilbronn challenge. This guide covers
what the app does, exact commands, a screen walkthrough, and the technical
architecture (challenge deliverable 4).

Status labels used throughout: **[observed]** = verified in the challenge CSV
(`docs/data_profile.md` is the data dictionary — do not duplicate it here) ·
**[predicted]** = model/solver output · **[demo assumption]** = labelled
synthetic value, configurable, not from data.

## 1. What the app does (plain language)

The city has 449 glass-collection locations with 1,338 container series
(location × colour: brown/green/white) recorded over 11,701 readings from
2025-10-17 to 2026-09-30 [observed]. The app answers three questions:

1. **Which containers will need emptying soon?** A persistence forecast
   (last known fill level) predicts the next reading per series.
2. **Which ones should we collect?** A threshold policy (default 80 % +
   always-include overfull) selects candidates and explains every skip.
3. **In what order should trucks visit them?** OR-Tools plans routes and
   recommends the fleet size; every numeric default is a visible
   [demo assumption] until the host supplies real values.

There is one active dataset in memory; uploading replaces it.

## 2. Setup, run, test, demo (exact commands)

Prerequisites: Python 3.14 (see `README.md` for versions), uv ≥ 0.13.1,
Node ≥ 26. Clean checkout needs **no API keys** (`.env.example` is optional
app settings only).

```bash
# backend
uv venv --python 3.14
uv pip install -e ".[dev]"
.venv/bin/uvicorn src.api.main:app --reload        # API on http://127.0.0.1:8000

# frontend (second terminal)
npm --prefix frontend install
npm --prefix frontend run dev                      # http://localhost:5173 (proxies /api/* to :8000)
```

Note: the Vite dev server answers on `localhost` (IPv6). In a terminal
`curl http://127.0.0.1:5173/health` fails (connection refused) while
`curl http://localhost:5173/health` returns
`{"status":"ok","service":"wasterouting-api"}` [observed live run 2026-11-14].
Open **http://localhost:5173** in a browser.

Checks (same as `.github/workflows/ci.yml`; all green 2026-11-14):

```bash
.venv/bin/ruff check .        # lint (use the venv binary — plain `ruff` may not be on PATH)
.venv/bin/mypy src            # strict type check → 0 issues in 35 files
.venv/bin/pytest              # backend tests → 404 passed
npm --prefix frontend test    # Vitest → 67 passed (16 files)
npm --prefix frontend run build
```

Comparison CLI (regenerates `docs/demo_numbers.md`):

```bash
.venv/bin/python -m src.api.compare_demo
```

## 3. Demo walkthrough (screens)

Start both servers, open http://localhost:5173. On the **Overview** page,
press **Load demo data** (loads the server-side demo CSV; the response labels
the source `demo:`) or upload `data/raw/glass_fill_levels_anonymized_f.csv`
via the upload panel. Both produce identical results.

### Overview
Three plain-language key numbers from the live API [observed live run
2026-11-14]: 34.5 % of readings are at/above the 80 % threshold, 10.2 % are
the literal `overfull` token (never coerced to 100), 0.0 % are numeric 0.
Shares are of **readings** — the data has no collection/emptying events
[observed]. Below: "Today's recommendation" (how many series are expected to
need emptying vs wait, with example reasons and the as-of date), a how-it-
works strip, and the **before/after comparison card** (three-step story,
§3.1).

### Three-step comparison story
Rendered from `GET /api/comparison` [observed live run 2026-11-14]; all
distances are haversine-straight-line-derived, **never road distance**:

| step | scenario | distance | served | m per kg |
|---|---|---|---|---|
| 1. Status quo sweep | `naive_sweep_all` (all 1,338 series, fixed area sweep) | 230,865 m | 78 / 1,338 | 5.6 |
| 2. Selection effect | `naive_sweep_selected` (policy-selected 458 only) | 262,995 m | 63 / 458 | 5.0 |
| 3. Optimised routing | `ortools` | 57,657 m | 40 / 458 | 2.4 |

Gains: selection **−32,130 m** (visiting fewer stops with the same sweep
order did not pay off per metre — the UI words negative gains honestly),
routing **+205,338 m**, total **+173,208 m**. Served counts differ between
scenarios by design, so the like-for-like comparison is the **m per
collected kg** column (5.6 → 5.0 → 2.4); never read raw distances as
equivalent.

### Containers
List of all 1,338 series with last reading date, last fill (numeric or
`overfull`, never coerced), and reading count.

### Forecast & candidates
Pick an as-of date (defaults: as_of 2026-09-30, horizon 28 days
[demo assumption — the observed median reading gap]) and method
(`persistence`; `rate` also available but worse: test MAE 25.77 vs 22.76 pp
[predicted, M5 evaluation]). The candidates panel shows selected vs skipped
series with reason badges (`at_or_above_threshold`, `overfull_state`,
`below_threshold`, `no_forecast`) and the deciding numbers in each detail
string. Demo run: 458 selected / 880 skipped [observed live run 2026-11-14].

### Route map
`POST /api/route` runs forecast → policy → geography → OR-Tools. The map
draws routes with numbered stops plus depot/disposal icons; the route panel
shows totals, load progression, the fleet recommendation, and **every
unserved stop with its reason** (never silently dropped). Demo run [observed
live run 2026-11-14]: status `feasible`, 3 routes, 40 served / 418 unserved,
57,657 m / 546 min, 47,880 L / 23,940 kg, fleet recommendation 63 ×
`demo_truck` (basis: ceil_by_volume 63, ceil_by_weight 38). A banner marks
the synthetic demo geography; coordinates are synthetic until the host
supplies real ones [demo assumption].

### Config editor
Edits 3 policy and 12 routing fields; empty = inherit the default. Every
default is tagged **[demo assumption]** via the `assumption_fields` list
from `GET /api/config` (fail-safe: if the list is missing, all fields are
labelled). Overrides never re-label a value as a fact.

### Technical details & determinism
The collapsible technical-details block shows the solver status and the
distance provenance (`haversine_straight_line_derived`). The optimised
scenario is solved 5 times [demo assumption]; the UI shows the determinism
mode: `identical` (all runs equal — the demo case, 57,657 m × 5) or
`median_of_runs` with min/median/max. A fired wall-clock safety cap produces
status `timeout`, which is explicitly non-reproducible and never shown as
deterministic.

## 4. Technical architecture

```text
challenge CSV ──► src/data (loader/validation) ──► src/analytics (EDA)
                        │
                        ▼
             src/forecasting (persistence/rate baselines)
                        ▼
             src/collection (threshold policy → candidates)
                        ▼
   src/routing (demo geography/fleet + OR-Tools solver) ──► src/api (FastAPI)
                                                            ▼
                                                   frontend (React dashboard/map)
```

Module responsibilities follow `PLAN.md`; cross-module shapes are pinned in
`docs/contracts.md`. API endpoints (contracts §5, all JSON snake_case,
routers under `/api`): `GET /health` (root + `/api/health`), `POST
/api/datasets` (CSV upload), `POST /api/datasets/demo`, `GET /api/summary`,
`GET /api/containers`, `GET /api/config`, `POST /api/forecasts`, `POST
/api/candidates`, `POST /api/route`, `GET /api/comparison`. Handlers are
thin; orchestration lives in `src/api/services.py`. Forecast approach:
deterministic persistence/rate baselines with leakage-safe features and a
chronological split (train < 2026-05-01, test ≥ 2026-08-01) — see
`docs/model_card.md`; ML (M6) was deferred because persistence (test MAE
22.76 pp [predicted]) set the bar. Routing approach: OR-Tools CVRP with
volume+weight dimensions, disposal unload-reset, droppable stops,
solution-limit stopping — full method in `docs/routing_methodology.md`.
Comparison design (scenarios, gains, repetition protocol): contracts §4.7.

## 5. Limitations (all labelled, not hidden)

- **One dataset in memory.** Uploads replace the active dataset; no
  persistence beyond the process.
- **Private raw CSV.** The challenge CSV is private and git-ignored: the
  **Load demo data** button, `POST /api/datasets/demo` and 17 real-data
  tests (real-CSV pins + demo-endpoint tests) require it at
  `data/raw/glass_fill_levels_anonymized_f.csv` (path is the server-side
  constant in `src/api/services.py`). On a clean checkout without the file,
  those tests skip with an explicit reason (`tests/helpers.py`) and the
  demo endpoint responds 404 by design — place the CSV at that exact path
  to enable both.
- **Synthetic geography, fleet and physics.** No coordinates, depot,
  disposal sites, vehicle specs, container volumes, densities, service
  times or shift rules exist in the data [observed]; all are
  [demo assumption] values in `src/routing/demo_config.py`, overridable
  per request.
- **Straight-line-derived distances.** Distances are haversine × 1.4
  detour factor [demo assumption]; there is no road-network data [observed].
  Never called road distance anywhere in the product.
- **No collection events.** The data records fill readings only [observed];
  shares are worded as "readings", never "emptyings".
- **Persistence baseline only.** M6 (ML) is deferred; persistence test MAE
  22.76 pp [predicted] is the current bar.
- **Solver determinism protocol.** Repeated solves that reach the fixed
  solution budget are identical; only a fired safety-cap timeout
  reintroduces wall-clock variance.
- **Small served share.** With demo fleet ×3 and 480-min shifts [demo
  assumption], most candidates remain unserved with reasons — honest
  feasibility surfacing, not a bug.
- **Python floor ≥3.12.** `requires-python = ">=3.12,<3.15"` because numpy
  2.5.4 requires ≥3.12 (earlier conflict with the 3.11 floor fixed in commit
  e6db442, 2026-11-14; `uv.lock` is committed so resolutions reproduce).
