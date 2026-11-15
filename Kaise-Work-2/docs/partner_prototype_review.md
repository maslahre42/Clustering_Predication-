# Partner prototype review — decisions per element

Status: architect decisions (2026-11-14), **verified against the partner
files** `data/from_partner/01_eda_and_analysis.ipynb`,
`03_fill_prediction.ipynb` and `src/predictor.py` (provided by the owner;
read 2026-11-14; never committed — git-ignored private material).
`src/clustering.py` (velocity computation, k-means) was **not** provided and
not inspected; the element-3 decision rests on the formula and its use in
`predictor.py`, which are visible. Nothing here changes
`docs/contracts.md` without user approval. Adopted ideas are re-implemented
in our codebase with tests and our conventions, and credited here and in
the relevant docs.

Decision legend: **Adopt** = take the idea as-is (re-implemented here) ·
**Adapt** = take the idea, changed to fit our contracts/honesty rules ·
**Reject** = do not take it (reason given; no silent omissions).

| # | element | decision | justification |
|---|---|---|---|
| 1 | Per-container profile (mean/std fill, overfull share, record count) | **Adapt** ⚠ | Cheap, fully [observed] descriptive stats that explain selection and feed a profile page; we adapt them to the emptying-record semantics (stats of *fill at emptying*), never coerce `overfull`, and label every number with its basis. |
| 2 | K-Means behavioural tiers (k=4, white glass only, names by rank) | **Reject** | Our M3 already tried k-means and it failed the interpretability gate (replaced by rule tiers 453/389/415/81, `docs/eda_report.md`); the partner's white-only k=4 variant was never validated and adds no routing decision value. |
| 3 | Fill velocity = median dF/dt over dF≥0 pairs; 0.65 %/day default for missing | **Reject** | Conflicts with the agreed data semantics: rows are emptying records, so fill *increases* between consecutive rows do not measure accumulation — the rate is `fill_at_emptying / interval`. The 0.65 %/day default is an unsourced fabricated value (AGENTS rule 2); series without data get "not enough data", never a default. |
| 4 | Linear forecast fill + velocity×days×holiday multiplier, capped at 110% | **Reject** | Depends on the rejected velocity; the 1.20 holiday multiplier has no demonstrated evidence; capping at 110 coerces `overfull` (violates contract §1.1/I3 never-coerce invariant). Our rate-at-emptying model (contracts v4 proposal) replaces it with honest lower-bound flagging. |
| 5 | Urgency classes Urgent ≥80 / Opportunistic 60–79 / Safe <60 | **Adapt** | Good plain-language vocabulary that matches our policy threshold 80 (§3.1); we adapt it as UI colour/badge classes driven by *our* predicted-fill/days-to-full values and our labelled config, not as a new scoring system. |
| 6 | Holiday logic: BW holidays, Dec 20–Jan 6, ±3-day windows, multiplier 1.20 | **Reject** (multiplier) — calendar awareness kept as open question | M3 observed 0 records on all 11 BW holidays; a *fill-rate* multiplier of 1.20 is unevidenced. Holidays legitimately affect *operating days* (no collections), which belongs in the scenario engine as non-operating days and in open questions — not as an invented demand multiplier. |
| 7 | Historical emptying audit (Late ≥100 / Optimal 70–90 / Premature 40–60 / Highly <40; 44.4% late, 26.2% premature, 4,266 events; derived from fill drops) | **Reject method, Adapt question** | The audit's classes are derived from fill *drops*, which the data semantics forbid using as emptying evidence. But the underlying question ("was the fixed schedule well-timed?") is exactly the provider's emptying-frequency priority: we answer it directly from fill-at-emptying records with corrected, gap-free bands (no 60–69/90–99 holes) in the scenario engine (task E). |
| 8 | `overfull` coerced to 110 in cleaning | **Reject** | Directly violates contract §1.1/I3 and M1/M2 tests: `overfull` is a distinct state, never a number; inventing the magnitude 110 is fabrication. Capped observations are flagged as lower bounds instead. |
| 9 | Container volume 2.5 m³, density 380 kg/m³ | **Split: Reject 2.5 m³, Adapt density to the sourced 0.40 t/m³ (400 kg/m³)** | 3 m³ is [representative] from the challenge representative (14 Nov) and authoritative over the partner's unsourced 2.5 m³. Density: owner rule was "use a German source if one exists, else 380" — a German AVV conversion table exists and gives **0.40 t/m³ for AVV 20 01 02 "Altglas (Flaschen-/Behälterglas, Depotcontainer)"** (entsorgen-versorgen.de, "Gewichte von Abfallarten, aufbereitet nach Sorte und AVV", retrieved 2026-11-14) — exactly our waste stream, and within 5 % of the partner's 380, which we keep as corroboration. Default becomes 0.40 kg/L [literature — German AVV table]; Q2 stays open for host-measured values. Volume still binds before weight, so routes/fleet counts are unchanged; kg totals drop ~20 % vs the old 0.5. |
| 10 | Gurobi MILP CVRP (licence-bound) | **Reject** | Gurobi needs a licence the hosted Render demo cannot rely on, and we already have an OR-Tools CVRP with volume/weight/compartments, honest status mapping and a deterministic stopping protocol (§4). No evidence exact MILP is needed at 1,338-stop scale. Credit: same CVRP-with-capacity formulation idea, already implemented here. |
| 11 | Folium route map, hardcoded Windows paths | **Reject** | We already ship a plain-Leaflet React map (M11) with synthetic-geometry labels; Folium is server-side HTML generation in the wrong layer for our SPA, and hardcoded Windows paths are a portability anti-pattern. |

## Verification of the owner's observations (verified against the files, 14 Nov)

- **0.65 %/day default is unsourced** — stands: the value is produced in
  `src/clustering.py` (not provided); nothing in `predictor.py` or the
  notebooks sources it. Not adopted.
- **Efficiency bands leave 60–69% and 90–99% mislabelled** — **verified in
  code** (`01_eda_and_analysis.ipynb` cell 12): the classifier buckets by
  `>=100 / >=70 / >=40 / else`, so a 95 % event is labelled "Optimal Window
  (70-90%)" and a 65 % event "Premature (40-60%)" — labels lie about the
  value they describe.
- **Fill-drop logic conflicts with the data semantics** — **verified in
  code** (cell 11): `emptying_events = df[df['fill_diff'] < 0]`; the audit's
  4,266 "emptying events" are drop-inferred, which the owner-stated
  semantics forbid.
- **`overfull` → 110 coercion** — **verified** (cell 2 markdown: overfull
  readings "assigned 110% for quantitative analysis"; `predictor.py`
  `.clip(upper=110.0)`). Direct §1.1/I3 violation — rejected.
- **Holiday rules and 1.20 multiplier have no demonstrated evidence** —
  **verified**: `1.20` appears only as a call parameter in `03_fill_prediction`
  cell 5 ("+20% surge during holiday periods") with no derivation; our M3
  EDA shows 0 records on all 11 BW holidays.
- **Tiers were never validated** — stands; additionally the tier construction
  lives in the unprovided `clustering.py`. Our M3 k-means independently
  failed an interpretability gate.

## Licence / authorship check

- **Gurobi**: commercial/academic licence required; size-limited free tier
  exists but is a deployment risk and adds no capability we lack. Rejected —
  no licence issue remains.
- **Partner code/ideas**: the partner is part of the same challenge team;
  ideas may be used with credit (this file + the relevant module docstrings).
  We re-implement rather than copy, so no third-party licence applies. The
  owner should confirm the partner is happy to have ideas credited here.

## Files requested — **provided and reviewed (14 Nov)**

`data/from_partner/01_eda_and_analysis.ipynb`, `03_fill_prediction.ipynb`
and `src/predictor.py` were supplied by the owner and read (code + markdown
cells; outputs skipped). `src/clustering.py` (velocity computation,
k-means tiers) was **not** provided — element 3's decision rests on the
formula and its use in `predictor.py`; element 2 stands on our own M3
evidence. The partner files stay uncommitted (private material,
git-ignored like `data/raw`).

## Research results feeding the v4 contract (14 Nov)

- **Density**: German AVV conversion table (entsorgen-versorgen.de, AVV
  20 01 02, hollow/container glass from depot containers) → **0.40 t/m³**;
  adopted as the labelled default. A second table (abfallscout.de, citing
  the Bavarian statistics office) gives 1.2 t/m³ for generic "glass" — that
  is a compacted/cullet figure, not loose igloo content, and is **not**
  used for our case.
- **Containers per site**: no German per-site container count found; the
  ZSVR advisory board (Aug 2024) recommends ≥1 glass collection site per
  1,000 inhabitants (site density, not per-site equipment). Heilbronn
  (~130k residents) would need ≥130 sites; 449 observed locations exceed
  that — consistent. Default `containers_per_site` therefore derives from
  the data structure: **one igloo per colour per location** (441/449 sites
  carry all three colours [observed]); duplicates of the same colour at one
  site are invisible to the data and remain a what-if multiplier
  [demo assumption].
