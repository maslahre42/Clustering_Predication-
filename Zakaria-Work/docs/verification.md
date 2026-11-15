# Verification of the corrected pipeline

Executed on 14 November 2026 in an isolated Python 3.12.13 environment with Gurobi 14.0.0, pandas 3.1.1, scikit-learn 1.9.1 and pytest 9.2.0. Gurobi was available: routing tests and example optimization actually ran rather than being skipped.

## Regression tests

**36 passed, no failures or skips.** The final full run took 1.64 seconds. A joblib warning about detecting physical macOS core count falls back to logical core count; it does not fail tests. Gurobi itself is configured to use one thread.

```sh
python -m pytest -q
```

Meaningful cases include invalid/duplicate readings, overflow without invented percentage, last-row integrity, material-specific identity, cycle-reset arithmetic, future-row invariance, same-day cutoff rejection, sparse/unknown forecasts, material fallback, identical clusters, per-bin decisions/site aggregation, missing/invalid coordinates, stable geometry across subsets, oversized demand without clipping, fleet shortage, impossible shifts, empty routing and configuration mismatch.

Solver verification also covers independently enumerating every order/partition of a small CVRP and matching the fleet/distance optimum; disconnected zero-demand cycles; weight binding before volume; shifts requiring extra trucks beyond the capacity lower bound; an infeasible bin-packing case only the solver detects; and final unloading/return time. Pipeline tests reconcile demo-deferred sites and verify source-byte preservation.

## Notebook execution

All five notebooks executed completely with nbclient and the isolated Python kernel. A total of 37 code cells executed without cell errors:

| Notebook | Result |
| --- | --- |
| `01_eda_and_analysis.ipynb` | Pass |
| `02_container_clustering.ipynb` | Pass |
| `03_fill_prediction.ipynb` | Pass |
| `04_gurobi_route_optimization.ipynb` | Pass, including actual Gurobi solve and Folium output |
| `main.ipynb` | Pass |

Executed copies were saved under `/tmp/zakaria-notebook-verification`; repository notebook outputs remain cleared so pre-correction plots/claims do not persist. Jupyter required local kernel sockets outside the filesystem sandbox. This was notebook execution, not a browser interaction check. The map was generated and its synthetic/direct-line captions and shared disposal coordinates were checked; no road-routing or browser map interaction is claimed verified.

To repeat notebook verification using your active Python environment, install `requirements-dev.txt` and run `python verify_notebooks.py --output /tmp/zakaria-executed-notebooks`. This helper supplies a kernel using the current interpreter, shuts it down after each notebook, and preserves clean notebook sources.

## Real-data example

```sh
python run_pipeline.py --planning-date 2026-08-17 --max-sites 24 --evaluate
```

The final example produced [the manifest](../data/corrected/manifest.json), [route rows](../data/corrected/routes.csv), [explicitly deferred sites](../data/corrected/deferred_sites.csv) and [the interactive map](../data/corrected/route_proposal.html).

| Measure | Observed result |
| --- | ---: |
| Source observation rows | 11,701 |
| Bins known strictly before 17 August | 1,337 |
| Selected bins | 207 |
| Selected physical sites | 108 |
| Explicit solver demonstration subset | 24 sites |
| Served in that subset | 24 sites |
| Solver-unserved in that subset | 0 |
| Deferred by explicit cap | 84 sites |
| Used one-load trucks | 9 |
| Modeled distance, synthetic geography | 171.7145 km |
| Combined truck working time | 13.5833 h |
| Estimated collected mass, assumed density | 50,668.90 kg |
| Gurobi runtime in the final example | 6.89 s |
| Status | Optimal under configured 2% MIP tolerance |

Thirteen and a half hours is the sum over nine trucks, not a single driver's shift. Every individual route stays below eight hours. The 84 deferred sites are outstanding selected service, not a claim that the whole city was served. Density, truck volume, locations and travel assumptions limit the operational meaning of these figures.

## Model-size optimization

For 24 sites and an upper bound of 12 vehicles, the original formulation would create `12 × (24² + 24) = 7,200` binary arc variables. The revised formulation actually creates **600** binary arcs and **672 total variables**, with **1,779 linear constraints**. This removes the vehicle multiplier from the arc model and reduces arc-variable count by 91.7% for this configuration.

The small exhaustive test checks mathematical equivalence on its fixture. The measured runtime above is a new-formulation run, not a controlled old-versus-new speed benchmark. Different candidate sets, gap limits, hardware and licenses can change time to solution.

## Chronological forecast evidence

[Metrics](../data/corrected/forecast_metrics.csv) and [cases](../data/corrected/forecast_cases.csv) are saved from rolling predictions at observed visits from 1 April through 30 September 2026. Each target-day prediction uses only observations strictly before that day. Earlier test visits can enter later histories.

| Method | MAE, pp | RMSE, pp | Common numeric scored cases |
| --- | ---: | ---: | ---: |
| Corrected cycle-median baseline | 19.5230 | 26.9685 | 5,306 |
| Last pre-emptying reading baseline | 25.5842 | 33.1762 | 5,306 |

The cycle median has approximately **23.7% lower MAE on those common numeric cases**. This is a comparison within this corrected evaluation, not a fair ranking against Omar's or Kaise's separately defined tests, nor a claim of improvement over a rerun of Zakaria's old forecast.

There are 6,731 target observations, including 693 explicit overfull truths, excluded from numeric error. Cycle forecasts exist for 6,657 cases and last-reading numeric baselines for 5,819; the common-case comparison prevents changing numeric coverage from creating a misleading advantage. Threshold confusion counts retain their own available-case coverage. The simple rate proxy treats censored readings as lower bounds and is not a probability-calibrated forecast. No measured route, overflow or CO₂ savings follows from this test.

## Source integrity

The source CSV is byte-for-byte identical to the original CSV in Git commit `b27bb42`:

```text
SHA256 cc23057e1600361d13dd668ae3f373197765bcb697543088741ba9f521d079ed
```

The original source CSV, municipal geographic references, legacy CSV exports, other contributors' implementations and `Solution/sql.db` were not modified by this correction task. Historical contributor/comparison reports received short links identifying that their Zakaria assessment predates this revision.
