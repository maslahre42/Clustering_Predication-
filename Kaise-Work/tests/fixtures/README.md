# Synthetic fixtures — NOT real data

Every file in this directory is **synthetic** (hand-authored for tests). No row
in these files originates from `data/raw/glass_fill_levels_anonymized_f.csv`,
which stays immutable under `data/raw/`.

## Isolation convention (M4, docs/eda_report.md)

- Every synthetic `Location_id` is prefixed `SYNTHETIC-` (e.g. `SYNTHETIC-acc-1`).
- Real challenge data uses UUID-format ids; `src.analytics.spatial.require_real_ids`
  fails any real-data code path that encounters a `SYNTHETIC-` id, so real and
  synthetic locations cannot be silently mixed.
- Files are named `synthetic_*.csv` to make the origin obvious at a glance.

## Files

| file | purpose |
|---|---|
| `synthetic_accumulation.csv` | hand-computable fill deltas/rates, overfull break, single-reading and flat-full series |
| `synthetic_seasonality.csv` | dates engineered around BW public holidays vs ordinary days, several months/weekdays |
| `synthetic_grouping.csv` | two well-separated behavioural groups + insufficient-history series |
| `synthetic_forecast.csv` | M5 hand-computable eval cases: overfull-break/rate pairs, overfull-only and single-reading series |
