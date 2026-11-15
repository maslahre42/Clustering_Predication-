# Model card — WasteRouting.AI forecasting

Status: v4 (2026-11-14, contracts §1.5/§2.3/§5.2.3 — emptying-record
semantics). **No trained model — persistence/rate baselines only.** ML was
deferred at M6 and stays deferred: complexity is adopted only if it beats the
better baseline below with chronological-split evidence. All numbers produced
by `.venv/bin/python -m src.forecasting.report` and `evaluate()` on the real
challenge CSV (run 2026-11-14); days-to-full aggregates by
`build_days_to_full` (pinned in `tests/forecasting/test_days_to_full.py`).

## Task

Predict the fill level (percent 0–100 + distinct `full`/`overfull` states) of
a glass-container series `(location_id, material_type)` at its **next
emptying record** after a prediction date (`as_of_date`). v4 semantics
(contracts §1.5, [representative-stated]): **one row is one emptying event**;
`fill_level_pct` is the fill observed at that emptying. Record intervals are
emptying intervals; fill drops are NOT emptying evidence and fill increases
are NOT accumulation velocity. Mandatory caveat: *"fill at emptying shows how
full the container was when the schedule reached it — not how fast it would
have filled"*; rates additionally assume no unobserved emptyings between
records.

## Data

`data/raw/glass_fill_levels_anonymized_f.csv` via the canonical loader
(contracts §1): 11,701 emptying records, 1,338 series, 2025-10-17 →
2026-09-30; 10,363 evaluation cases (one per record with a prior record).
Overfull is a distinct token (1,192 rows) — never coerced (§1.1).

## Split (chronological — never random)

train `< 2026-05-01` (4,571) · validation 2026-05-01..07-31 (3,722) ·
test `>= 2026-08-01` (2,070). Protocol choice for the prototype, not a brief
fact.

## Features (leakage-safe: only records with date ≤ as_of_date; `features.py`)

last numeric fill, last-record-is-overfull flag, days since last record,
per-series mean/max numeric fill, overfull share, n records, month,
**`fill_at_emptying_rate_pct_per_day`** = median over records `r_i` (i ≥ 2)
with `interval_days = date_i − date_{i−1} > 0` and numeric `fill_i` of
`fill_i / interval_days` (§1.5 — never Δfill/Δdays), and
**`median_interval_days`** = median consecutive interval > 0 (date-based;
overfull records participate). Missing values are explicit `None`, never
imputed.

## Baselines (deterministic; `baseline.py`)

- **persistence**: last observed numeric fill; `overfull` last record →
  state `overfull`. Unchanged from M5.
- **rate** (v4 redefinition, §2.3): expected fill at the next emptying =
  per-series §1.5 accumulation rate × the series' median observed interval,
  clipped to [0,100]. No usable rate ⇒ **no numeric prediction** (`None`;
  never a persistence fallback, never a default rate).

## Results (MAE/RMSE in percentage points; numeric truths only — overfull
truths never coerced)

| method | split | scored / cases | skipped | overfull truths | MAE | RMSE |
|---|---|---|---|---|---|---|
| persistence | validation | 3,364 / 3,722 | 10 | 348 (9.3 %) | 27.658 | 34.991 |
| persistence | test | 1,943 / 2,070 | 2 | 125 (6.0 %) | 22.764 | 30.475 |
| rate (v4) | validation | 3,221 / 3,722 | 168 | 348 | **25.391** | **32.185** |
| rate (v4) | test | 1,930 / 2,070 | 15 | 125 | **20.146** | **25.857** |

State detection (`full-or-overfull`, threshold 80 % — **demo assumption**),
test split: persistence TP 424 / FP 336 / FN 349 / TN 959; rate TP 419 /
FP 272 / FN 353 / TN 1,011.

**v4 headline: the rate baseline now beats persistence on both splits**
(test MAE 20.146 vs 22.764; validation 25.391 vs 27.658) — the pre-v4
Δfill/Δdays rate was worse (25.77/34.00 test); under emptying-record
semantics the fill-at-emptying rate is the stronger signal. Any M6+ model
must beat **20.146 pp test MAE** (or justify itself otherwise) to be adopted.
Rate coverage is lower (168/15 cases skipped for no usable rate) — surfaced,
never silently dropped.

## Days-to-full v2 (`days_to_full.py`, contracts §5.2.3 — not a trained model)

Consumed downstream by the §5.2.4/§5.2.5 scenario engine (per-series rates
drive both strategies) and the per-container interval view; method details:
`docs/routing_methodology.md` §8–§9, demo numbers: `docs/demo_numbers.md`.

Per series: `rate_pct_per_day` = §1.5 median fill-at-emptying rate;
`days_to_full = target_pct / rate` (target 90 % **[demo assumption — slide
mockup]**; parameter 1..100), assuming the container **refills from 0 after
each emptying** [model assumption]; `predicted_full_date = last_emptying_date
+ round(days_to_full)` — never clamped (may be overdue). Overfull/numeric-100
candidates are censored lower bounds (§1.5): they never enter the numeric
median but set `is_lower_bound`. Reasons — no estimate ever fabricated:
`not_enough_records` (< 2 records), `zero_interval_only`, `no_numeric_fill`,
`zero_rate` (rate exactly 0; contract addendum 2026-11-14).

Real-CSV aggregates (target 90): 1,338 series, **1,303 with an estimate**;
median **59.3 d**, mean 101.7 d, min 6.6, max 2,313.0;
`lower_bound_share_pct` **66.5** (868 series flagged). Per material (median
days / estimates / lower-bound share): brown **121.95** / 422 / 36.3 %;
green **52.0** / 439 / 73.6 %; white **38.05** / 442 / 88.5 %. Reasons: 34
`not_enough_records`, 1 `no_numeric_fill`; no `zero_rate`/`zero_interval_only`
cases. White/green containers need emptying far sooner and are far more often
censored — consistent with profile §15.

## Honest findings and limitations

1. MAE ~20–28 pp is high — expected for decile-quantized, visit-driven
   emptying records with ~28 d median gaps; forecasts are a prioritisation
   signal, not a precise level gauge.
2. The rate estimate inherits the §1.5 caveat: fill at emptying is what the
   schedule observed, not free-accumulation velocity; unobserved extra
   emptyings would deflate rates and inflate days-to-full.
3. 66.5 % of days-to-full estimates are censored lower bounds (true demand ≥
   estimate) — days-to-full is an upper bound on time-to-target for those
   series.
4. Overfull truths are excluded from numeric metrics by design; state metrics
   carry them. Skipped cases (persistence 10/2, rate 168/15) are counted,
   not hidden.
5. Evaluation happens only at observed emptying records — there is no
   counterfactual "what if not visited" ground truth.
6. Threshold 80 %, target 90 % and inference horizons are demo assumptions,
   configurable.
7. `zero_rate` is a contract addendum (architect-approved 2026-11-14) beyond
   the §5.2.3 v2 three-reason enum; zero occurrences on the real CSV.
