# Model card — WasteRouting.AI forecasting

Status: M5 baseline section (2026-11-14). ML model section added at M6 only if
it beats the baseline with evidence. All numbers produced by
`.venv/bin/python -m src.forecasting.report` (exit 0, verified by architect).

## Task

Forecast the fill level (percent 0–100 + distinct `full`/`overfull` states) of a
glass-container series `(location_id, material_type)` at its **next observed
reading** after a prediction date (`as_of_date`). Target/horizon rationale:
docs/contracts.md §2.1 (readings exist only at visit dates — median gap 28 d).

## Data

`data/raw/glass_fill_levels_anonymized_f.csv` via the canonical loader
(contracts §1): 11,701 readings, 1,338 series, 2025-10-17 → 2026-09-30.
10,363 evaluation cases (one per consecutive reading pair with history).

## Split (chronological — never random)

train `< 2026-05-01` (4,571) · validation 2026-05-01..07-31 (3,722) ·
test `>= 2026-08-01` (2,070). Protocol choice for the prototype, not a brief fact.

## Features (leakage-safe: only readings with date ≤ as_of_date)

last numeric fill, last-reading-is-overfull flag, days since last reading,
per-series mean/max numeric fill, overfull share, n readings, month, per-series
median numeric-pair rate (pp/day). Missing numeric history = explicit `None`,
never imputed. `src/forecasting/features.py` (reviewed: filter at line 81).

## Baselines (deterministic; `src/forecasting/baseline.py`)

- **persistence**: last observed numeric fill; `overfull` last reading →
  state `overfull`.
- **rate**: last numeric fill + median numeric-pair rate × horizon days,
  clipped to [0,100]; falls back to persistence without a numeric pair.

## Results (MAE/RMSE in percentage points; numeric truths only — overfull
truths never coerced, reported separately)

| method | split | n | overfull truths | MAE | RMSE |
|---|---|---|---|---|---|
| persistence | validation | 3,364 scored / 3,722 | 348 (9.3 %) | **27.66** | 34.99 |
| persistence | test | 1,943 scored / 2,070 | 125 (6.0 %) | **22.76** | 30.48 |
| rate | validation | 3,364 | 348 | 30.46 | 38.20 |
| rate | test | 1,943 | 125 | 25.77 | 34.00 |

State detection (`full-or-overfull` at threshold 80 % — **demo assumption**),
test: persistence TP 424 / FP 336 / FN 349 / TN 959; rate TP 397 / FP 316 /
FN 376 / TN 979.

## Honest findings

- **Persistence is the headline baseline**: the rate baseline is worse on both
  splits (validation +2.8 pp, test +3.0 pp MAE). Complexity must beat 22.76 pp
  test MAE at M6 to be adopted.
- MAE ~23–28 pp is high — expected for decile-quantized, visit-driven readings
  with ~28 d gaps; forecasts are a prioritisation signal, not a precise level
  gauge (see limitations).
- Skipped cases (no numeric history): 10 validation / 2 test — surfaced, not
  dropped silently.

## Limitations

1. Reading semantics unresolved (data profile §13.1): we cannot tell
   collection resets from measurement variation; rates mix both directions
   (EDA: increases 40.8 % vs decreases 40.7 %).
2. `overfull` truths are excluded from numeric metrics by design; state
   metrics carry them.
3. Evaluation only at observed readings (no counterfactual "what if not
   visited" ground truth).
4. Threshold 80 % and inference horizons are demo assumptions, configurable.
