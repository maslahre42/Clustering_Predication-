# Review of Zakaria-Work-2

Reviewed the uploaded folder on 15 November 2026 against `Zakaria-Work` and the current integrated `Solution`. This review uses the uploaded files, not an assumed GitHub branch head. `Zakaria-Work` already contains earlier local corrections, so differences against it are not a clean history of Zakaria's own commits. Neither contributor folder nor the application implementation was changed by this review.

## What Zakaria added that is worth keeping

The upload develops the project into an analytical story: understand collection behavior, explain groups and forecasts, distinguish routing improvements from selection-policy changes, and demonstrate operations visually. Those are useful contributions independently of whether every headline number is currently defensible.

| Addition | Assessment | Best use in our solution |
| --- | --- | --- |
| Material-specific cadence, filling-speed and time-to-full analysis in notebook 01 | Useful explanatory analysis. Separates visit spacing from filling behavior and includes quartiles and hotspot rankings. | Extend **Understand past collections** with median/IQR days between visits, cycle-rate distributions, observed-cycle time-to-full projections, and location/material drill-down. |
| Cluster-quality comparisons and seed stability | Reproducible diagnostics rather than choosing four groups only by presentation. | Add the quality/stability evidence to behavioral group details, retaining sparse-history and separation gates. |
| Chronological forecast diagnostics | Actual-versus-predicted scatter, residual distribution and urgent precision/recall help users judge errors. | Add matched-case diagnostics alongside our model comparison, using the same cutoff and scoring rules for each model. |
| Experiment A versus Experiment B | Strong experimental distinction: route the same selected demand to evaluate routing, then separately study what selection changes do to service. | Add a controlled fixed-order/nearest-neighbor/optimized benchmark; keep policy replay with missed urgent service and deferred demand visible. |
| Independent route verification and solver metadata | Good engineering direction: reconstruct distance/time and disclose solver status, gap, bound and runtime. | Keep our compact Gurobi check and multi-load road router; extend verification to independently recompute every physical load and shift. |
| Executive dashboard and chronological map replay | Clear visual hierarchy, station inspection, timeline controls, animated collection/reset behavior, truck tracking and presentation tour. | Use the visual ideas with real request results, explicit coordinate provenance and our existing street paths. Keep observed events distinct from estimated fill between events. |
| Payload yield, fuel and emissions views | Useful supplementary operating indicators if assumptions are explicit. | Compute kg/road-km and optional fuel/CO2 estimates from actual plan totals and entered factors. Do not import fixed coefficients or annual savings claims. |

## Changes against the current local folder

Ignoring environment/cache directories: **11 added, 16 changed, 20 absent** relative files. Added code includes `dashboard.py`, `src/simulator.py`, `src/generate_dashboard_data.py`, and `tests/test_audit_compliance.py`; there are also standalone executive/twin HTML views and dashboard/cache data. The modules and all five notebooks differ. The upload does not include the earlier corrected runner, evaluation module, 36-test suite, notebook verifier, method/verification documents or `data/corrected/` artifacts. That is a comparison of snapshots, not an attribution of deletions to a particular author.

## Findings reproduced from the uploaded data

### 1. Grouping is repeatable, with moderate separation

Recomputed on the upload's white-glass profiles:

| k | Silhouette | Davies–Bouldin | Calinski–Harabasz |
| --- | ---: | ---: | ---: |
| 3 | 0.2453 | 1.2844 | 176.62 |
| 4 | 0.2533 | 1.1389 | 169.84 |
| 5 | 0.2317 | 1.2248 | 153.92 |

For four groups and seeds 42, 7, 123, 999, 2026: mean pairwise adjusted Rand index **0.9618**, minimum **0.9260**, maximum **1.0000**. This supports stability across initializations. It does not establish temporal stability, balanced groups or validated service-frequency recommendations. Four groups lead silhouette and Davies–Bouldin in this small comparison; three lead Calinski–Harabasz. The silhouette value indicates limited separation, so the notebook's strongest “mathematical optimality” language should be softened.

Sources: `Zakaria-Work-2/src/clustering.py:128`, `:153`, `:187`, notebook 02.

### 2. Forecast validation is useful but cannot rank our models directly

Reproduced white-glass chronological split: **3,169 training / 812 test cases**, training through 28 July 2026, test 29 July–30 September. Reported model MAE **17.81 percentage points**, versus **26.63** for its former cumulative baseline; the upload calls this **33.1% improvement**. Its explicit-overfull-excluded subset has **728 cases** and MAE **16.59**. Urgent recall/precision are **67.6% / 80.2%**; explicit-overfull recall/precision are **60.7% / 24.5%**.

These reproduce its scoring procedure, including a numeric 110% proxy for explicit overfull. Its “uncensored” subset still includes numeric 100%, which our contract treats as a lower bound. Its comparison baseline, white-only scope, dates and fitting protocol differ from our integrated evaluation, so these figures are not evidence that this model beats Omar's or Kaise's on matched cases.

Profiles have no cutoff parameter; callers must trim observations before fitting. The dashboard reads persisted intermediates without a shared cutoff/fingerprint check. Keep our request-local snapshot rules when adopting these views. Unknown values, unsupported histories and lower bounds need the existing explicit states rather than invented rates/percentages.

Sources: `src/predictor.py:101`, `src/clustering.py:49`, `src/data_loader.py:6` in the uploaded folder.

### 3. Collection-cadence analysis needs careful labels

Notebook 01 correctly uses each recorded visit as a reset, then estimates rate as fill divided by elapsed days. Its new cadence distribution, boxplot, time-to-full curve and hotspot/slow-bin tables are good candidates to adopt.

Corrections needed before integration:

- Explicit overfull is converted to 110%; it must remain a category/lower bound. Time-to-full from such a cycle is not an exact observed time.
- The cumulative curve pools **cycles**, while its axis labels describe **containers**. Containers with more visits therefore receive more weight.
- `total_visits` in the per-container exported summary counts completed intervals, omitting the first actual visit. Display recorded collections and completed cycles separately.
- `(~4 wks)` is appended to every median cadence, regardless of the computed value. Treat 28 days as an optional comparison line, not proof of a fixed historical schedule.
- Numeric rates below full describe completed cycles; extrapolating them to 100% assumes unchanged filling speed.
- “Optimal (70–90%)” actually includes 70 through below 100%; “Premature (40–60%)” includes 40 through below 70%. Use correct ranges and descriptive labels rather than assuming every low-fill visit was wasteful.
- The original `main.ipynb` and README still include negative-difference emptying detection and older forecasting descriptions, inconsistent with the revised notebook 01. Identify the authoritative method before reuse.

Sources: notebook 01 cells 11–17; `main.ipynb`; README.

### 4. Geographic alignment is deterministic but unverified

`align_demands_and_coordinates` sorts anonymized UUIDs and municipal POI IDs, pairs the first entries by rank, and joins that bridge. This passes row-shuffle tests but does not establish that the bins are at those locations. Adding a UUID can change existing pairings.

The supplied demand file has **448 rows**, while only **109** are mapped to coordinates; **339** are outside the mapped demonstration. Within the mapped 109, **50** are forecast urgent, but the selected subset is 24. **30 urgent sites are deferred**, including **10 forecast at 100% or more**. The dashboard data's own deferred audit lists a maximum fill of **107.9%** alongside “0 bins (Safe buffer).” This contradicts the zero-overflow/complete-critical-service headline.

The simulator also synthesizes and clips coordinates for the 449-location registry, and indexes stream-specific profiles by location alone. Preserve location/material identity and synthetic/unverified labels. Our public street routing must not infer a real UUID-to-street match from sorted order.

Source: `src/optimizer.py:12`, `:71`; `src/simulator.py:123`; `data/dashboard_data.json`.

### 5. Dashboard totals are partly fixed demonstration data

`src/generate_dashboard_data.py` contains literal truck summaries, Experiment A/B results, annual savings and executive KPI values. The Streamlit scenario section changes arithmetic around fixed **27.08 versus 6.45 hours** and **398.6 versus 87.0 km**. Changing its urgency slider does not call the forecasting/routing engine. These are presentation examples, not live recalculated optimization results.

Defaults such as 2.5 m³ containers, 9 t payload, 6-minute service and €500 truck-day differ from our applied assumptions. Keep prices, density, fuel and emissions coefficients editable and explicitly sourced. Full-shift charges, per-hour prorating and packed truck counts represent different cost models; `ceil(total hours / shift)` is only a lower bound on a feasible physical schedule.

Sources: `src/generate_dashboard_data.py:65`, `:206`, `:347`; `dashboard.py:695`.

### 6. The animation cannot substantiate zero overflow or street-distance savings

The twin is a useful presentation prototype, but its dynamic mode:

- Caps every accumulated fill at **96%**, then reports `active_overflows_today = 0` explicitly. Zero overflow is imposed by construction.
- Uses Haversine distance × **1.10**, while historical mode uses Haversine × **1.35**. The modes do not use the same street-distance model.
- Uses nearest-neighbor/local route sequencing rather than the Gurobi MILP claimed in its description.
- Does not enforce the configured payload/shift/compartment constraints before resetting serviced bins.
- Uses profiles/statistics computed over the full dataset to replay earlier dates, and pools material state in the station registry.

Rebuilding the payload in isolation produced **223 dynamic routes over our 12 t limit**, with a maximum summed stop weight of **19,973.2 kg**. Maximum simulated fill was exactly **96.0%** and all reported overflow counts were zero. These results confirm that the current animation is not a valid operational benchmark. Reuse its timeline, inspection and animation concepts with our common digital twin and road paths.

Sources: `src/simulator.py:238`, `:373`, `:482`, `:535`, `:605`.

### 7. Route verification needs independent load reconstruction

The new auditor recomputes travel distance/time but checks reported volume/weight fields instead of rebuilding them from selected demand. A three-node test with 2.5 m³ actual demand, a 1 m³ capacity and falsely reported zero load passed its audit. Its fixed-order baseline also scheduled that oversized 2.5 m³ pickup under a 1 m³ limit. The greedy baseline can repeatedly open empty trips when no remaining pickup fits.

The verification idea is worth keeping; use independent per-bin demand sums, real route geometry/costs, final unloading and return, shift constraints, material chambers and exact served ownership. Keep missed/unreachable/oversized pickups explicit in every baseline.

Source: `src/optimizer.py:384`, `:435`, `:553`.

## Executed checks and limits

- Ran the upload's **11 audit tests** in a temporary copy: **9 passed; 2 failed because the 24-site, four-vehicle model exceeds the installed size-limited Gurobi license**. The upload does not catch that exception. This is not evidence that its mathematical model is infeasible or wrong; the large case was not verified here.
- Independently ran its Gurobi model on a deterministic three-site fixture within the license limit: **optimal, two trucks, all three sites served, 7 km on the supplied test matrix**. The distance/time audit passed for that valid fixture. This is a toy matrix check, not a road-service benchmark.
- Recomputed the cluster-quality/stability and forecast metrics above from the raw upload.
- Checked demand/coordinate mapping, urgent/deferred counts, an oversized baseline pickup, the understated-load audit case, and rebuilt the full twin payload in isolation.
- Opened both supplied HTML dashboards in Edge. Both rendered without page JavaScript errors. The basemaps showed **API-key-required tiles** in this environment; map tiles were not successfully verified. No Streamlit server or full notebook execution is claimed.
- Contributor sources, source data, SQLite and application behavior were preserved. This review adds documentation only.

## Recommended adoption order

1. **Understand past collections:** material cadence distributions, rate distributions, estimated filling-time distributions and bin/material rankings, with counts, bounds and cutoff shown. Use product-focused labels and explanations without contributor credits.
2. **Evidence:** cluster stability and actual-versus-predicted/residual diagnostics on matched, cutoff-safe data. Preserve descriptive rather than guaranteed service tiers.
3. **Benchmarks:** same-demand fixed-order/nearest-neighbor/optimized routing with identical road matrices and enforced constraints; keep selection-policy trade-offs separate.
4. **Presentation:** replay dates and animate real collection resets/truck progress over our street paths. Label interpolated states and hypothetical demand; retain missed urgent collections.

This preserves Zakaria's analytical structure and visual ideas while connecting the results to the integrated app's data, forecast, constraints and route evidence.
