# Demo script — SmartWasteRouting (M13–M16, v4 semantics + scenario engine)

Goal: a 5-minute reproducible end-to-end story on real challenge data with
every assumption visibly labelled — **cost-first, but service level is
always shown beside every cost** (§6). Numeric beats follow the generated
comparison in `docs/demo_numbers.md` (reproduce:
`.venv/bin/python -m src.api.compare_demo`; scenario-engine numbers from
live `POST /api/scenarios` / `POST /api/simulation`, recorded in the same
file).

## Setup (pre-demo, from clean checkout)

```bash
uv venv --python 3.14 && uv pip install -e ".[dev]"
npm --prefix frontend install
.venv/bin/uvicorn src.api.main:app --reload &        # :8000
npm --prefix frontend run dev &                      # http://localhost:5173 (proxies to :8000)
```

Note: the Vite dev server answers on `localhost` (IPv6); in a terminal use
`curl http://localhost:5173/health`, not `127.0.0.1` [observed 2026-11-14].

## Opener

Start in **presentation mode** (6 slides, ←/→, Esc, fullscreen). It pulls
every number from the live API and keeps all honesty labels on screen —
[observed]/[predicted]/simulation basis, straight-line distance, the
[representative]/[literature]/[demo assumption] tags. Load demo data first
(opener slides include the KPIs); a slide whose data is missing says so
explicitly — never a fabricated number.

## Beats

1. **Load data** — on Overview, press **Load demo data** (server-side demo
   CSV, labelled `demo:`) or drag `data/raw/glass_fill_levels_anonymized_f.csv`
   into the upload panel. KPIs appear [observed]: 11,701 **emptying records**
   (DE "Leerungsdaten"), 449 locations, 1,338 series,
   2025-10-17..2026-09-30; 34.5 % of emptying records at/above 80 %, 10.2 %
   the `overfull` token (never coerced), 0.0 % empty. Say the semantics out
   loud: **one row = one emptying event** [representative-stated, written
   confirmation pending] — and the caveat: fill at emptying shows how full
   the container was when the schedule reached it, not how fast it would
   have filled.
2. **Before/after card (four-step comparison story)** — from
   `GET /api/comparison`, `docs/demo_numbers.md`: ① status quo
   `naive_fixed_frequency` 355,474 m, 60/637 series due under the 28-d
   cycle [demo assumption, Q10]; ② sweep-all upper bound
   `naive_sweep_all` 454,623 m, 50/1,338; ③ selection effect
   `naive_sweep_selected` 527,021 m, 38/458 — **negative selection gain
   −72,398 m, worded honestly ("did not pay off")**; ④ optimised
   `ortools` 70,175 m, 34/458, routing gain +456,846 m, total +384,448 m.
   Point at the m-per-kg column (10.5 → 12.6 → 13.2 → 3.9) as the
   like-for-like view; never equate raw distances. In the flat 10-min
   travel mode, visiting order cannot change duration (§4.4) — savings
   come from stop *selection*, not ordering. Cost beats, all [predicted]
   derivations — never invoiced, **always shown with the observed service
   anchor 26.9 % of emptying records full/overfull [observed]**: each
   scenario 1,500 EUR/day (3 trucks × 500 EUR/truck-day [representative])
   / 300,000 EUR/year (× 200 operating days [representative]); fleet
   budget 99 × `demo_truck` = 49,500 EUR/day / 9,900,000 EUR/year,
   covering full demand incl. unserved stops. Technical details:
   determinism `identical` ×5 (70,175 m each); distances are
   haversine-straight-line-derived (density 0.40 kg/L [literature — AVV
   20 01 02]), never road distance.
3. **Scenarios tab (cost-first story)** — sliders for the planning levers
   (cycle 28 d [Q10], containers per series [Q11], truck-day cost, shift,
   vehicle volume; all initialised from the config defaults). Live numbers
   [observed run 2026-11-14]: fixed_frequency **426,000 EUR** (852
   truck-days, 15,636 emptyings) but **2.4 % overflow container-days and
   14.4 % of simulated emptyings at/overfull**; demand_driven
   **520,000 EUR** (1,040 truck-days, 9,993 emptyings) with **zero
   overflow, max fill exactly the 80 % trigger**. The honest punchline:
   demand-driven **costs more** — its emptyings cluster onto shared peak
   days (rate-synchronised series come due together), so peak days need
   more trucks despite fewer total emptyings. Never read the cost column
   without the service column (§6). On the timeline, point at the
   **mega-day note**: series without pre-window history start at fill 0 on
   the same day → ~12 synchronised mega-days of ~1,303 emptyings — a
   replay artefact of the §5.2.5 initialisation rule, not observed
   behaviour. TechDetails: calibration echo simulated fill-at-emptying
   median 42.5 % vs observed 60.0 %.
4. **Containers, forecasts & days-to-full** — pick as_of 2026-09-30
   (horizon 28 [demo assumption: the observed median emptying interval]);
   the **rate** baseline now leads under v4 semantics: test MAE 20.15 pp vs
   persistence 22.76 pp [predicted, chronological split,
   `docs/model_card.md`]. Then the per-container interval view
   (`GET /api/days-to-full` — the representative's reporting wish):
   1,303/1,338 series with an estimate, median 59.3 d, mean 101.7 d, min
   6.6, max 2,313.0 d, 66.5 % flagged **censored lower bounds** ("at
   least" markers) [predicted]; per-material medians brown 121.95 / green
   52.0 / white 38.05 days — white/green need emptying far sooner. Say the
   caveats: target 90 % [demo assumption], refill-from-0 model assumption,
   rates assume no unobserved emptyings between records — indicative, not
   a schedule.
5. **Candidates** — threshold 80 + overfull rule [demo assumption]; 458
   selected / 880 skipped [observed] with reason badges; tweak the
   threshold live in the config editor to show adaptivity.
6. **Route** — map with numbered stops, depot/disposal icons; status
   `feasible`, 3 routes, 34 of 458 served / 424 unserved **each with a
   reason**, 70,175 m / 580 min, 45,000 L / 18,000 kg; fleet
   recommendation 99 × `demo_truck` (basis: 99 by volume, 48 by weight);
   scenario cost 1,500 EUR/day [predicted] beside the 26.9 % anchor
   (`docs/demo_numbers.md`, ortools scenario). The physics behind it are
   all labelled: 3,000 L containers and 5 min emptying [representative],
   10 min per leg incl. depot/disposal (interpretation, Q4), 8 h shift
   [representative]; equal-third compartments, fleet specs [demo
   assumption]; density 0.40 kg/L [literature]. Banner: "synthetic demo
   geography — straight-line derived distances, NOT road distances"
   (`haversine_straight_line_derived`).
7. **Honesty slide** — observed vs predicted vs [representative] /
   [literature] / [demo assumption] legend (`docs/contracts.md`). Split
   the host inputs: **answered verbally 14 Nov 2026** → [representative]:
   3 m³ containers; 5 min emptying; 10 min between containers; 8 h shift;
   500 EUR/day, 5 days/week, 200 days/year; one vehicle type serves all
   materials, collected separated. **[representative-stated]**: one row =
   one emptying event (written confirmation pending). **[literature]**:
   density 0.40 kg/L (German AVV table AVV 20 01 02, retrieved
   2026-11-14). **Still open** (`docs/open_questions.md` Q1–Q11): truck
   capacity + fleet count (Q1), measured densities (Q2), compartment
   layout (Q3), is the 10 min flat/average and does it cover
   depot/disposal legs (Q4), per-container vs per-location emptying (Q5),
   real coordinates (Q6), road-network matrix (Q7), disposal unload
   duration (Q8), the provider's unnamed second key graph (Q9), the real
   emptying schedule/frequency (Q10), multiple same-colour igloos per site
   (Q11).

## Closer

Return to presentation mode's final slide (comparison + scenarios side by
side): "cost is half the story — every cost here is shown with its service
level, and the numbers you saw are reproducible with the commands in the
user guide."

## Rules

- Never present straight-line-derived distances as road distances.
- Never present defaults as facts: [representative] values came verbally
  from the host; [literature] values cite their source; [demo assumption]
  values are placeholders — the config panel keeps the per-field source
  labels visible; overrides never re-label a value as fact.
- **Every cost figure is shown with its service level** (§6) — the observed
  anchor 26.9 % beside scenario costs, the simulated overflow/full shares
  beside strategy costs. Cost is never shown alone.
- Human wording is "emptying records" / "Leerungsdaten" — never
  "readings"/"measurements"/"sensor" (JSON field names keep the historical
  `readings` tokens).
- Negative gains are shown as negative (e.g. selection −72,398 m), never
  spun.
- Never present cost figures as invoiced amounts — they are [predicted]
  derivations from the [representative] cost parameters.
- If the solver returns infeasible/timeout, show the unserved reasons —
  that is the product working as designed. A fired wall-clock safety cap
  means status `timeout` and the run is explicitly not reproducible.
- Unserved stops are never silently dropped.

## Fallback

- If upload fails: **Load demo data** (same server-side CSV, labelled).
- If a live solve is slow: the fixed solution budget (200 [demo
  assumption]) stops the solver deterministically; the 30 s wall-clock cap
  is a safety net that would show as an honest `timeout`.
- If the live API is unavailable mid-demo: presentation mode already
  rendered slides from the earlier responses; a slide whose fetch failed
  shows "data not available" rather than a stale or fabricated figure.
