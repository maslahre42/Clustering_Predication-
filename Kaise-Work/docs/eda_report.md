# EDA report — glass fill-level readings (M3) + spatial/container analysis (M4)

Status: data-engineer M3+M4 (one pass per PLAN hackathon note), finished and
reviewed 2026-11-14. All numbers below are **observed**, produced by:

```bash
.venv/bin/python -m src.analytics.report
```

(run on `data/raw/glass_fill_levels_anonymized_f.csv` via the canonical loader,
contracts.md §1; exit 0). Units: fill level in **percent 0–100** plus the literal
`overfull` state; gaps in **days**; period **2025-10-17 → 2026-09-30**.
Code: `src/analytics/` (holidays, series_features, seasonality, grouping,
spatial, figures, report), tested in `tests/analytics/` (synthetic fixtures are
prefixed `SYNTHETIC-`, isolated under `tests/fixtures/`).

## 1. Observed results

### Coverage
- 11,701 rows; brown 3,100 / green 4,169 / white 4,432; 1,338 series; 34
  single-reading series; median of per-series median gaps 35.0 d; median
  per-series mean fill 61.0 %.
- Gaps between consecutive readings: n=10,363, median 28.0 d, max 272 d.

### Accumulation (descriptive only — see §3)
- 8,328 numeric consecutive pairs: increasing 40.8 %, decreasing 40.7 %, flat
  18.5 %; mean delta +0.28 pp; median rate 0.0 pp/day; mean positive rate
  +1.10 pp/day; mean negative rate −1.65 pp/day.

### Seasonality (count | mean fill % | overfull share | BW holidays in month)
| month | count | mean fill | overfull share | BW holidays |
|---|---|---|---|---|
| 2025-10 | 741 | 55.3 | 0.004 | 0 |
| 2025-11 | 656 | 58.4 | 0.021 | 1 |
| 2025-12 | 1,357 | 62.5 | 0.010 | 2 |
| 2026-01 | 783 | 71.6 | 0.116 | 2 |
| 2026-02 | 657 | 71.5 | 0.129 | 0 |
| 2026-03 | 776 | 70.2 | **0.376** | 0 |
| 2026-04 | 896 | 73.9 | 0.233 | 2 |
| 2026-05 | 951 | 63.9 | 0.227 | 3 |
| 2026-06 | **1,501** | 50.7 | 0.052 | 1 |
| 2026-07 | 1,310 | 58.8 | 0.050 | 0 |
| 2026-08 | 1,215 | 56.0 | 0.028 | 0 |
| 2026-09 | 858 | 58.6 | 0.106 | 0 |

Seasons: winter 2025/26 mean fill 66.9 %; spring 2026 mean fill 69.1 % with
overfull share 0.273; summer 2026 most readings (4,026) but lowest mean fill
54.9 %.

### Weekdays
Readings/day: Mon 39.2, Tue 46.3, Wed 51.3, Thu 45.4, Fri 43.5, Sat 8.9,
Sun 0.4.

### Public holidays (EXTERNAL CALENDAR INPUT — deterministic computus, not dataset)
- 11 BW holidays in span (2025-11-01 … 2026-06-04, listed in report output).
- **Readings/day on holidays = 0.000** vs 34.6 off holidays; weekday-matched
  ratio 0.00 → zero readings fall on any BW public holiday.
- School vacations (BW): **not analysed — dates not verifiable locally**;
  remains an open question.

### Container grouping
- Seeded k-means (k∈2..4) rejected by the interpretability gate (silhouette /
  size / IQR separation; gate output in report: `chosen_k=None`) →
  **rule-based pressure tiers** used instead:
  high 453 · medium 389 · low 415 · insufficient_history 81 (eligible 1,256).
- Tier profiles (medians): high — 10 readings, gap 29 d, mean fill 77.8 %,
  overfull share 0.158, share-at-100 0.308; medium — 8 readings, gap 34 d,
  60.0 %, 0.083, 0.125; low — 6 readings, gap 43 d, 36.7 %, 0, 0;
  insufficient — 2 readings, gap 111 d.

### M4 — spatial
- Canonical schema has 5 fields, **0 coordinate-like**; no coordinates exist in
  the source (data profile §13.8). No spatial clustering is possible from this
  file; geography must come from the host or be a labelled demo assumption.
- Synthetic isolation: `SYNTHETIC-` id prefix + `tests/fixtures/` README;
  `src/analytics/spatial.py` guards (`is_synthetic_id`, `require_real_ids`)
  verified in tests — real and simulated locations cannot be confused.

### Figures (docs/figures/, titles carry units + period)
`fig_monthly_readings_holidays.png`, `fig_fill_value_distribution.png`,
`fig_gap_days_distribution.png`, `fig_delta_vs_gap_scatter.png`,
`fig_weekday_rates.png`, `fig_grouping_profiles.png`.

## 2. Interpretation (separate from observation — hypotheses, not conclusions)

1. Zero holiday readings + Mon–Fri weekday pattern + per-visit batching
   (profile §16) together indicate **readings are taken during working-visit
   rounds** — consistent with, but not proof of, §13.1 "reading at visit".
2. Overfull share peaks in Jan–May (max Mar 2026, 0.376) with high mean fill —
   plausibly post-winter accumulation; Dec-2025 volume peak co-occurs with
   Christmas (12-25/26) but no causal claim is made.
3. The Jun–Aug 2026 volume peak is **not** explained by public holidays (0–1
   per month) — candidate drivers: season, onboarding, or collection-policy
   change; unresolved.
4. Fill-rate proxies are crude: increases and decreases balance (40.8/40.7 %)
   because visits likely reset levels; true accumulation between collections
   cannot be estimated without knowing which visits emptied containers (§13.1).
5. Pressure tiers give M7 a ready, explainable priority signal (high tier:
   mean fill 77.8 %, share-at-100 0.308).

## 3. Open questions carried forward
§13.1 reading semantics (gates M5 target definition) · BW school vacation
dates (external input needed) · Jun–Aug 2026 driver · coordinates/depot/fleet
absent (M8 must source or label demo assumptions) · overfull semantics (§13.2).
