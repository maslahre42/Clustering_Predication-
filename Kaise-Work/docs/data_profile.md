# Data profile — `data/raw/glass_fill_levels_anonymized_f.csv`

Status: M1 source audit (data-engineer), 2026-11-14.
Environment: Python 3.14.8, pandas 3.1.1 (repo `.venv`).
Scope: **only this CSV was audited.** The other files in `data/raw/`
(`20261113_Readme Challenge PZ.pdf`, `PreZero.pdf`) were **not** read or audited.
`data/raw/` is immutable; nothing in this audit wrote to it.

## Reproduction

Commands cited below:

- `H` = `head -c 600 data/raw/glass_fill_levels_anonymized_f.csv | cat -v`
- `W` = `wc -l data/raw/glass_fill_levels_anonymized_f.csv`
- `P` = `.venv/bin/python -m src.data.profile_glass_fill`
  (source: `src/data/profile_glass_fill.py`; prints every aggregate fact below,
  verified by `tests/data/test_profile_glass_fill.py` on a labelled synthetic fixture)

Every fact below is **observed** (produced by the cited command) unless marked
*(derived)* = arithmetic on observed numbers, or **open question** = unresolved
semantics. Raw CSV was never read whole; only aggregates were computed.

## 1. File & encoding (observed, H/W)

- CSV, comma-separated, 1 header row + 11,701 data rows (`W` → 11,702 lines).
- UTF-8 **with BOM** (`H` shows BOM bytes before `Location_id`). Loaders must use
  `encoding="utf-8-sig"` or the first column name gets a BOM prefix.

## 2. Columns & types (observed, H, P)

| column | as-read (text) | inferred type / meaning |
|---|---|---|
| `Location_id` | UUID-like string, e.g. `0004c095-29ec-…` | identifier of a glass container location |
| `material_type` | string | categorical: exactly `brown`, `green`, `white` (glass colours); no case/whitespace variants |
| `date` | string `YYYY-MM-DD` | calendar date, ISO-8601, **date-only** |
| `fill_level_perc` | **mixed**: integers and the literal string `overfull` | fill level; name implies percent |

Note: with pandas default inference `fill_level_perc` becomes `object` dtype
(ints + str mixed). `Location_id` has no leading/trailing whitespace (P:
`LOCATION_IDS with padding/whitespace: 0`).

## 3. Units (partly observed, partly name-implied)

- `fill_level_perc`: unit "percent" is **implied by the column name** and
  consistent with the observed numeric range 0–100 (P: `numeric range: min=0
  max=100`). The supplier nowhere states the unit in this file.
  All numeric values are multiples of 10 (P histogram, §8) — i.e. quantized to
  10-percentage-point buckets.
- No other measurable quantity exists in the file. Coordinates, volumes,
  weights, densities, depot/fleet data are **absent** (open question §13.8).

## 4. Timezone (undeterminable from data)

Dates are date-only strings with no time or UTC-offset component
(P: `date-only strings; no time component`). **Timezone is undeterminable from
data.** Whether dates are local (Europe/Berlin) collection-day dates is an open
question (§13.6).

## 5. Record grain (observed, P)

One row = one fill reading for one (`Location_id`, `material_type`, `date`):
- exact-row duplicates: **0**
- duplicate rows on the full key (`Location_id`,`material_type`,`date`): **0**
- keys with conflicting fill values: **0**
So the key is unique — at most one recorded reading per series per calendar day.

## 6. Time span & coverage (observed, P)

- Min date 2025-10-17, max date 2026-09-30; 229 distinct dates.
- Span covers 349 calendar days *(derived)* → readings exist on ~66% of days.
- 0 non-null-unparseable dates (strict `%Y-%m-%d` parse).

## 7. Entities (observed, P)

- 449 distinct `Location_id`s; 1,338 distinct series (`Location_id`×`material_type`).
- Locations by number of materials: **441 have all 3** (brown+green+white),
  7 have 2, 1 has 1. 98.2% *(derived)* of locations carry all three materials.
- Readings per series: min 1, p25 5, median 8, p75 12, max 37.
- 34 series have exactly one reading (P `TRANSITIONS`).

## 8. Fill-level values (observed, P)

- 10,509 numeric readings; **1,192 literal string `"overfull"`** (10.2% of rows,
  *derived*); **0 other/unexpected text**; no other missing values (§9).
- Numeric range 0–100; **0 out-of-range** values.
- Histogram (value → count, all multiples of 10):
  `0:2, 10:450, 20:1090, 30:1091, 40:1019, 50:855, 60:1097, 70:870, 80:1114, 90:968, 100:1953`
  (sums to 10,509 *derived*). Notably `100`×1,953 and `0`×2.

## 9. Nulls (observed, P)

0 missing values in every column (11,701 × 4 cells all populated).

## 10. Duplicates (observed, P)

0 exact-row duplicates; 0 key-level duplicates; 0 conflicting keys (§5).

## 11. Invalid / out-of-range (observed, P)

0 unparseable dates; 0 numeric fills <0 or >100; no values other than numeric
deciles and `overfull` in `fill_level_perc`; material values exactly
{`brown`,`green`,`white`}.

## 12. Outliers / anomalies (observed unless noted, P)

1. `"overfull"` token (1,192 rows) makes the column mixed-type — a data-quality
   finding; it must not be silently coerced to a number.
2. Longest gap between consecutive readings of one series: **272 days** in
   series `fe0e3e24-b563-460e-a113-39dda882939c` / `brown` (that series has 3
   readings total — one-off targeted pandas query, reproducible snippet below).
3. 34 single-reading series; per-series median gap reaches 265 days (§12.4).
4. Only 2 readings equal 0 across the whole file — near-empty containers are
   almost never observed (see also §12.5).
5. After a full (`100`) or `overfull` reading, the next reading of the same
   series is **never 0** (minimum next value observed: 10); 41.2% *(derived,
   1,179/2,865)* of full/overfull readings are followed by another `100` or
   `overfull`.

Reproducible snippet for §12.2 row count:

```bash
.venv/bin/python -c "import pandas as pd; df=pd.read_csv('data/raw/glass_fill_levels_anonymized_f.csv',encoding='utf-8-sig',dtype=str); print(((df.Location_id=='fe0e3e24-b563-460e-a113-39dda882939c')&(df.material_type=='brown')).sum())"
```

## 13. Open questions (questions, not guesses)

1. **What does one reading represent** — a sensor spot-check, a driver reading
   at collection, or a level observed on a visit? Evidence for discussion: 93.4%
   *(derived, 4,175/4,468)* of same-day (location,date) pairs span ≥2 materials
   (§14), suggesting visit-driven batch readings, yet 41.2% of full/overfull
   readings are followed by another full/overfull (§12.5), so collection does
   not reliably reset the value.
2. **What exactly does `"overfull"` mean** — measured >100%, an overflow
   report, or a sensor-error flag? How should forecasting/routing treat it
   (censor to 100? treat as >100? separate category)?
3. **Is `100` censored** ("full or more") rather than exactly 100%?
4. **Is `Location_id` one physical container, or a site/address with up to
   three material sub-containers?** 98.2% of locations have all three materials
   (§7) — if one container per location, a location could not hold three
   materials simultaneously.
5. **Why are numeric values always multiples of 10** — source rounding, export
   bucketing, or manual entry? Do finer-grained values exist upstream?
6. **Which timezone/calendar do the dates refer to?** Undeterminable from data (§4).
7. **What causes long gaps (up to 272 d) and single-reading series** — no
   collection needed, unmonitored periods, decommissioned/new containers?
8. **Where must coordinates, depot, fleet, container volumes/weights, service
   times come from?** They are absent from this file; PLAN.md expects them from
   the challenge host.
9. **Are the PDFs in `data/raw/`** (`20261113_Readme Challenge PZ.pdf`,
   `PreZero.pdf`) **authoritative for units/semantics?** Flagged; out of audit
   scope, not read.
10. **Can multiple collections of one series occur on one day?** The file holds
    at most one reading per series per day (§5); whether multiple same-day
    events are collapsed upstream is unknown.

## 14. Measurement intervals per `Location_id`×`material_type` (observed, P)

Distribution of gaps (days) between consecutive readings within a series
(10,363 gaps *derived* = 11,701 rows − 1,338 series first readings):

- All gaps: min 1, p25 18, median 28, p75 42, max 272.
- Most common gap values: 13–15 d, 19–22 d, 27–28 d → consistent with roughly
  2-, 3- and 4-week revisit cadences.
- 58.6% of gaps ≤ 31 days (P `gaps<=31d_share=0.586`).
- Per-series median gap: min 7, median 35, max 265 days → cadence varies
  strongly per container/material.

## 15. Per-material row counts & value usage (observed, P)

- Rows: `white` 4,432; `green` 4,169; `brown` 3,100 (sum 11,701 *derived*).
- `overfull` rows by material: white 731, green 357, brown 104 → 16.5% / 8.6% /
  3.4% of the material's rows *(derived)*.
- Share of numeric readings equal to `100`: white 30.8%, green 17.7%, brown 4.7%.
  White/green containers hit full/overflow far more often than brown.

## 16. Same-day batching & monthly volume (observed, P; interpretation deferred to M3)

- (location, date) pairs: 4,468 total *derived* — 3,061 read all 3 materials the
  same day, 1,111 read 2, only 296 read 1 → readings arrive in per-visit batches.
- Rows per month: 2025-10:741, 11:656, 12:1357, 2026-01:783, 02:657, 03:776,
  04:896, 05:951, 06:1501, 07:1310, 08:1215, 09:858 (sum 11,701 *derived*).
  Peaks: Dec-2025 and Jun–Aug-2026; troughs: Nov-2025/Feb-2026. Whether this is
  seasonal effect, onboarding artefact or collection policy is **M3 work**, not
  a conclusion here.

## 17. Known facts (pre-verified, reconfirmed by P)

11,701 rows; columns `Location_id,material_type,date,fill_level_perc`; UTF-8
BOM; 449 unique `Location_id`s; materials brown/green/white; dates
2025-10-17→2026-09-30; fill values = deciles 0–100 in steps of 10 plus literal
`overfull`×1,192; `100`×1,953; `0`×2; no missing fields. All match §2–§11.

## 18. Handoff notes for downstream milestones (M2 loaders / M5 features)

- Read with `encoding="utf-8-sig"`; read `fill_level_perc` as text first, then
  split into numeric value + boolean `is_overfull`; **never coerce `overfull`
  to a number silently**.
- Enforce key uniqueness (`Location_id`,`material_type`,`date`) in validation
  (observed unique here, §5).
- Parse dates strictly `%Y-%m-%d`; treat date-only as timezone-less (§4).
- Model series as (`Location_id`,`material_type`); irregular intervals are the
  norm (median gap 28 d, p75 42 d) — feature code must handle irregular spacing.
- This file contains **no** coordinates/depot/fleet inputs — M8 must source them
  separately and label them as assumptions until the challenge host supplies data.

## Open-question protocol

None of §13 is resolved by guessing. Answers should come from the challenge
brief/host (on site at HHN), the `data/raw/` PDFs once audited, or explicit
demo assumptions labelled as such per AGENTS.md rule 3.
