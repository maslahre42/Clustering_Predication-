# Three projects, one solution: comparison, merge plan and corrections to the Codex review

Written 14 November 2026 (Saturday evening) for the PreZero challenge, Future City Hackathon.
Covers `Omar-Work/`, `Kaise-Work/`, `Zakaria-Work/` and the Codex document
`docs/project-comparison-and-combination.md`. Monir's `Solution/` is mentioned only where it matters
for the merge; I did not review its code.

**What I checked myself today:** I read the code and docs of the three projects, ran Omar's tests
(6 of 6 pass) and Zakaria's tests (36 of 36 pass, Gurobi included), and ran Omar's planner for
17 August 2026 in two ways to measure one of the bugs Codex reported. I did not run Kaise's project
(it needs Python 3.11 or newer; the sandbox has 3.10), so everything about Kaise comes from her code
and her saved reports.

---

## 1. Short answer

1. **Use Omar's app as the demo and the engine.** It is the only project that already runs on the
   numbers PreZero gave on 14 November (3 m³ containers, 12 t per load, 10 minutes between
   containers, 5 minutes per container, 8-hour shift, Monday to Friday), and it already covers all
   four deliverables in one screen flow.
2. **Take from Kaise:** strict upload checking with clear error messages, a reason for every
   container (selected, skipped, not served), the German/English labels, and her user guide.
3. **Take from Zakaria:** the analysis notebooks and charts, the real Heilbronn glass-site list for
   the map, and the Gurobi model as an independent check of the OR-Tools routes on a small case.
4. **Fix three things in Omar's code first** (section 5). They are small.
5. **Agree on one set of numbers.** Today the three projects answer "how many trucks?" with 3, 9
   and 63. The difference comes from assumptions, not from the data (section 3).

Codex recommends the opposite base: Kaise's React/FastAPI app with Omar's engine put inside. That is
a clean design, but it needs an adapter between two different data models (Kaise plans per
container, Omar per site) with less than a day left. This is a team decision; my view is that the
risk is too high for the time available. Section 6 lists what else Codex got wrong or left out.

---

## 2. What each project is

| | Omar | Kaise | Zakaria |
|---|---|---|---|
| Form | Python package + Streamlit app | FastAPI backend + React frontend, Docker | Notebooks + Python pipeline + HTML map |
| Upload | Yes, flexible; bad rows are dropped silently | Yes, strict; rejects the file and lists every error | CLI `--csv`; rejects invalid rows |
| What a reading means | Fill **before** emptying; every visit empties (PreZero's answer) | Left open ("semantics unresolved") | Same as Omar (after the correction) |
| "Overfull" | At least 100% (censored) | Separate state, no number | Separate state, no number |
| Forecast | Fill-rate model per container with season and vacation effects; gives a **probability of overflow** | Persistence: next reading = last reading | Median fill rate per container × days since emptying |
| Which containers to empty | Overflow risk ≥ 70% before the next collection day; neighbours at the same site from 40% fill | Predicted fill ≥ 80% | Predicted fill ≥ 80%; neighbours from 60% |
| A stop is | A site (all colours together) | One container; the three colours of a site get **different** map positions | A site |
| Router | OR-Tools; weight, volume, shift; **several loads per truck** | OR-Tools; weight, volume; shift checked after solving | Gurobi exact model; weight, volume, shift; **one load per truck** |
| Fleet answer | Fewest trucks that serve all mandatory stops | Total volume ÷ truck volume | Trucks used by the model |
| Extra | Settings page, backtest against the historical schedule | Typed API contracts, tests, DE/EN, deployment guide | Clean EDA, grouping, 109 real Heilbronn glass sites |

All three read the same file the same way: 11,701 readings, 449 sites, 1,338 containers,
17 October 2025 to 30 September 2026. That is about eleven and a half months, not "over a year".

---

## 3. The differences that matter

### 3.1 The numbers do not match

| Setting | Omar | Kaise | Zakaria (current) | PreZero said |
|---|---|---|---|---|
| Container volume | 3 m³ | 1.9 m³ | 3 m³ | 3 m³ |
| Glass density | 350 kg/m³ | 500 kg/m³ | 350 kg/m³ | not given |
| Truck payload | 12 t | 10 t | 12 t | 12 t |
| Truck volume | no limit | 12 m³ | 18 m³ | unknown |
| Trucks available | up to 12 | 3 | up to 12 | "enough" |
| Shift | 8 h | 8 h | 8 h | 8 h |
| Driving | 10 min fixed | from synthetic coordinates | 10 min fixed | 10 min |
| Time per container | 5 min | 10 min per stop | 5 min | 5 min |
| Unloading | 15 min | 30 min | 15 min | not given |

"PreZero said" is taken from the notes in Omar's README; I cannot confirm them independently.

The truck volume is the hidden problem. At 350 kg/m³, an 18 m³ truck is full at 6.3 t, so
Zakaria's trucks carry about half of the 12 t PreZero named. Kaise's 12 m³ at 500 kg/m³ gives 6 t.
Omar uses the 12 t limit only.

### 3.2 Same question, three answers

| | Omar | Zakaria | Kaise |
|---|---|---|---|
| Planning day | 17 Aug 2026 | 17 Aug 2026 | 30 Sep 2026, 28 days ahead |
| Selected | 43 mandatory sites, 109 optional | 108 sites (207 containers) | 458 containers |
| Routed | 49 sites, 122 containers, 105 t | 24 sites (demo limit), 50.7 t | 40 containers, 23.9 t |
| Trucks | **3** (9 loads, 22.6 h in total) | **9** (one load each, 13.6 h in total) | 3 used; recommends **63** |

Omar's row is my run today with the model trained only on data before 17 August. Zakaria's row is
his saved verified run. Kaise's row is her saved demo report.

Why they differ:
- Zakaria needs 9 trucks for 24 sites because each truck does one load and is full at 6.3 t.
- Kaise's 63 is total volume divided by one truck load. It ignores that a truck can unload and
  continue, so it is a number of loads, not a number of trucks.
- Omar lets a truck unload and continue, so 3 trucks do 9 loads.

Do not show these three results side by side to the jury. Pick one configuration first.

### 3.3 Forecast quality is closer than it looks

| Project | Method | Test period | Mean error (points of fill) |
|---|---|---|---|
| Omar | Rate model, trained once up to 31 March | Apr to Sep 2026 | 19.5 (simple container median: 21.3) |
| Zakaria | Container median rate, updated every day | Apr to Sep 2026 | 19.5 (last reading: 25.6) |
| Kaise | Last reading | Aug to Sep 2026 | 22.8 |

These are not scored on exactly the same cases, so they are not a fair ranking. Zakaria leaves out
"overfull" visits and updates his rates daily; Omar scores every visit with a model frozen in March.
Two conclusions are still safe:

- Treating each visit as an emptying (Omar, Zakaria) beats "next reading = last reading" (Kaise).
- Omar's advantage is not the average error. It is the **overflow probability**, which the
  selection rule needs, and better behaviour for containers with few readings.

A likely cheap win for Omar: refit the model every planning day instead of freezing it in March.
Zakaria's daily-updated simple baseline already matches the frozen model.

### 3.4 Kaise's stops are containers, not sites

Kaise gives each container its own synthetic position, made from site ID plus colour. White, green
and brown at the same site end up at three places on the map, and the truck "drives" between them.
441 of 449 sites have all three colours, so this affects almost every stop. Her 10 minutes of
service is also per container stop. This is the main reason her routing cannot be reused as it is.

---

## 4. How to combine

### 4.1 Target

```
Upload CSV
  -> Kaise's validation (reject bad files, show each error)
  -> Omar's data step (cycles between emptyings)
  -> Patterns page: Omar's charts + Zakaria's material and group charts
  -> Omar's forecast (overflow probability per container)
  -> Omar's selection, with Kaise-style reason text for every container
  -> Omar's router (several loads, shift, fewest trucks)
  -> Map on Zakaria's real Heilbronn sites, labelled as illustrative
  -> Export route sheet per truck (Monir's manifest idea)
Side evidence: Omar's backtest + Zakaria's Gurobi check on a small case
```

### 4.2 What to take from whom

| From | Take | How |
|---|---|---|
| Omar | App, forecast, selection, router, settings page, backtest | Stays as the base |
| Kaise | `src/data/loader.py` validation | It is plain Python: call it on the uploaded file before Omar's loader and show its error list |
| Kaise | Reason per container | Add a "reason" column to Omar's selection table: due, neighbour at a visited site, optional, skipped, not served |
| Kaise | DE/EN labels, user guide, Docker notes | Reuse the wording; merge her guide with Omar's README into one guide |
| Zakaria | EDA notebooks, material table, group charts | Show in the Patterns page or as slides |
| Zakaria | `data/heilbronn_actual_glass_containers.csv` (109 real glass sites) | Use as map positions. Say clearly that the link between anonymous site IDs and real places is made up |
| Zakaria | Gurobi model | Run it and Omar's router on the same 24 sites with the same settings and one load per truck. One slide: "the fast router is within X% of the exact optimum" |
| Monir | Route sheet export, historical viewer | If time allows; otherwise show his app as a second screen for history |

### 4.3 Order of work

1. **Everyone, 15 minutes:** agree on the settings in section 3.1. Proposal: PreZero's numbers,
   density 350 kg/m³, no truck volume limit, 15 minutes unloading.
2. **Omar:** the three fixes in section 5.
3. **Kaise:** upload validation and the reason column in Omar's app; merged user guide.
4. **Zakaria:** Gurobi check with the agreed settings; charts for the Patterns page; site list for
   the map.
5. **Monir:** route sheet export and the architecture diagram.
6. **Everyone:** one demo script: upload, patterns, forecast, change truck payload from 12 t to 8 t,
   see the plan change, show the backtest.

### 4.4 What to claim in the pitch

Safe, all from Omar's saved backtest (April to September 2026, simulated):
- Same service level with 19% fewer site visits and 11% fewer truck-days.
- Or the same effort with 24% less time that containers sit full.
- Share of collections below 40% full drops from 31% to 20%.

Say openly:
- It is a simulation, not a measured saving.
- The number of overflow events does **not** go down. Without live sensors a single filling cycle
  cannot be predicted well.
- For forecast quality use the forward test: AUC 0.78, error 19.5 points. Omar's README currently
  shows 0.84 and 16.5, which come from random splits and look better than what a real planner would
  get. Change the README and the slides to the forward-test numbers.

---

## 5. Fixes needed in Omar's code

| # | Problem | Where | Effect today | Fix |
|---|---|---|---|---|
| 1 | The app trains the model on all data, also data after the chosen planning day | `app.py`, `_model()` | On 17 Aug: 36 mandatory sites instead of 43; 305 containers selected instead of 354. The backtest is **not** affected | Train on cycles that end before the planning day |
| 2 | Containers first seen after the planning day are still planned | `app.py`, route planner `state` | 1 container on 17 Aug | Build `state` from `known`, not from `df` |
| 3 | If the solver finds no solution, all stops are returned as "optional skipped" and the fleet search stops | `routing.py`, `if sol is None` | Rare: every stop can be skipped, so a solution almost always exists | Return mandatory sites in `dropped_mandatory` |
| 4 | A site larger than one truck load is cut down to the truck size without a warning | `routing.py`, `np.minimum(...)` | None with current settings: the biggest site is 3.15 t against 12 t. With payload 2 t: 33.2 t of glass reported as 29.0 t | Raise an error or split the site |

---

## 6. Corrections to the Codex document

**Wrong or out of date**

1. **Zakaria's settings table (Codex section 4).** Codex lists 2.5 m³ containers, 380 kg/m³,
   9,000 kg payload and a 7.5 h shift. Zakaria's current run uses 3 m³, 350 kg/m³, 12,000 kg and
   8 h (`Zakaria-Work/data/corrected/manifest.json`). Only the 18 m³ truck volume is still right.
2. **Zakaria's method (Codex sections 2, 3 and 7).** The body still describes the old version:
   linear extrapolation with a holiday multiplier, a fake 110% for overfull, white glass only, an
   empty result when the solver fails. All of this was replaced. The note at the top of the Codex
   document says so, but the tables below it were not updated and contradict it.
3. **"Zakaria's forecast should stay an experiment."** After the correction his simple forecast has
   the same average error as Omar's model (section 3.3). It is a useful, transparent baseline.
4. **"Kaise-Work is untracked."** It is now committed (`dec7e27`, "all project combined").
5. **"Nothing was executed."** True for Codex. Tests for Omar and Zakaria now pass in a clean
   environment (section top).

**Right in the code, but overstated**

6. **Oversized demand (fix 4).** Codex says it "currently invalidates some outputs". It cannot
   happen with the current settings.
7. **No-solution handling (fix 3).** Real, but it is a rare path, not a normal one.

**Right and confirmed**

8. **Training on future data in the app (fix 1).** Confirmed and measured. Codex did not say how
   large the effect is or that the backtest is clean.

**Missing**

9. **Truck volume.** Codex says "reconcile the defaults" but does not notice that the volume limits
   in Kaise's and Zakaria's projects cut the load to about 6 t, half of PreZero's 12 t. This alone
   explains most of the gap in truck counts.
10. **Which numbers are confirmed.** Codex treats all four configurations as equal assumptions.
    PreZero confirmed several on 14 November; those are not open for discussion.
11. **Omar's headline forecast numbers** come from random splits (section 4.4).
12. **Time.** The five-step plan (versioned datasets, shared contracts, common evaluation) is good
    engineering but does not fit before the deadline. Section 4.3 is the short version.
13. **The base.** Codex picks Kaise's app as the base. See section 1 for why I would not, and note
    that this is a judgement, not a fact.

**Still correct in Codex and worth keeping:** one interface only; one meaning for a reading; never
turn "overfull" into 110%; planning for day D uses only data before D; report unserved stops openly;
do not add up or mix the projects' result numbers.

---

## 7. Housekeeping

- `fillinq-router/` in the repository root only contains an old `.venv` and is not tracked. Add it
  to `.gitignore` or delete it.
- The same CSV is stored three times (Omar, Zakaria twice). Keep one copy after the merge.
