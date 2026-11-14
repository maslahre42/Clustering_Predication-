# WasteRouting.AI readiness review

**Historical review:** this document records issues found before integration. For the current connected implementation, corrected semantics, executed checks and remaining prototype limits, use the [challenge handover](challenge-demo-guide.md) and [integration contract](combined-project-integration.md).

Reviewed 14 November 2026 against [the challenge brief](../challenge.pdf).

**Assessment: there is a credible hackathon prototype here, with useful evidence and reusable code. The main work is correcting evaluation and routing edge cases, then presenting one connected workflow. The current evidence does not establish operational savings or production readiness.** The brief explicitly welcomes a prototype concept; it does not require a finished production deployment.

## What was reviewed

1. [Exploratory notebook](../../main.ipynb): all 22 cells and saved text outputs.
2. [PreZero Germany research report](../../PreZero_Germany_report.pdf): all 12 pages, including its source register. This review assessed its role and distinctions between facts, examples and assumptions; it did not independently revalidate every external reference.
3. [Python forecasting and routing prototype](../../fillinq-router/README.md): ingestion, forecasts, selection, routing, simulation, dashboard, tests and saved results.
4. The current Nuxt/API application's forecast integration view and relevant product documentation.
5. Read-only checks of `sql.db` and the router CSV. Their historical observation rows match exactly.

No source data or implementation was changed by this review. The Python model, optimizer and backtest were not rerun: the available Python runtime lacks pandas, SciPy, scikit-learn, OR-Tools and pytest. Forecast and simulation numbers below are saved project results, cross-checked for interpretation and arithmetic, rather than newly reproduced results. No browser verification was performed.

## Contribution of each piece

| Piece | Useful contribution | Assessment |
| --- | --- | --- |
| Notebook | Material comparisons, exploratory charts, initial groups and a proposed workflow | Keep the descriptive findings; correct the emptying, rate and overfull assumptions before using its headline conclusions. |
| Research PDF | Operational inputs, chamber constraints, equipment compatibility, uncertainty and a data-request plan | Useful specification material. Its local examples are not confirmed Heilbronn assets or a verified PreZero fleet inventory. |
| Python project | CSV upload, probabilistic forecasting, site selection, OR-Tools routing, configurable operations and simulation | The strongest reusable implementation. It needs correctness fixes, a cleaner benchmark and integration with the chosen demonstration UI. |

These pieces complement each other. They are not three independent validations of the same efficiency claim.

## Evidence that supports the concept

The source contains **11,701 readings at 449 locations**, representing **1,338 observed location/material pairs**. Do not assume all 449 locations have all three observed materials: that would imply 1,347 pairs.

Coverage runs from **17 October 2025 to 30 September 2026**, less than a full year, despite the brief's broader description. The saved quality report shows a median of eight readings per container and a median 28-day gap. This limits what can be concluded about daily dynamics and recurring annual seasonality.

Independently recalculated from `raw_data`:

| Glass material | Readings | Explicit `overfull` | Numeric 100% or explicit `overfull` | Numeric 30% or less |
| --- | ---: | ---: | ---: | ---: |
| White | 4,432 | 16.49% | 42.22% | 4.78% |
| Green | 4,169 | 8.56% | 24.71% | 14.68% |
| Brown | 3,100 | 3.35% | 7.87% | 58.35% |

These are shares of **recorded readings at visits**, not shares of all days, network-wide live occupancy or directly measured accumulation. Numeric 100% is full; it is not automatically a confirmed overflow incident.

Nevertheless, the imbalance is a clear reason to test material-specific selection: white glass often needs attention while brown glass is frequently collected at low fill. The data alone does not prove why the operator made those visits or that every low-fill collection was avoidable.

### Forecast evidence

From [saved forecast metrics](../../fillinq-router/results/forecast_metrics.json):

| Evaluation | Model MAE, percentage points | Per-container median-rate baseline MAE | Model AUC for fill at least 70% | Baseline AUC |
| --- | ---: | ---: | ---: | ---: |
| Random cycle cross-validation | 16.49 | 17.36 | 0.840 | 0.818 |
| Chronological test, training before 1 April 2026 | 19.54 | 21.31 | 0.785 | 0.735 |

The chronological test contains 6,657 observations. Its model MAE is approximately **8.3% lower** than the stronger per-container baseline. This is a useful, measured improvement on held-out readings. Lead with these chronological numbers rather than presenting random-fold results as future-dispatch performance.

The model treats full/overfull readings as censored and pools sparse containers toward material-level behavior. Those are better starting choices than inventing exact overflow percentages. Its AUC measures discrimination for a **70% fill threshold**, not confirmed future overflow detection. Calibration and interval coverage still need checking before interpreting a forecast probability as a service guarantee.

### Simulation evidence and trade-offs

Recalculated relative changes from [the saved routed summary](../../fillinq-router/results/routed_summary.csv):

| Measure | Scenario labelled same service | Scenario labelled same effort |
| --- | ---: | ---: |
| Site visits | -22.8% | +3.9% |
| Simulated container-days full | +0.8% | -24.8% |
| Simulated overflow events | +9.1% | +4.5% |
| Distance | +2.6% | +18.6% |
| Driver hours | -5.2% | +14.6% |
| Truck-days | -25.3% | -11.6% |

This supports exploring a **service/cost trade-off**, not claiming every outcome improves. The scenario names are approximate comparisons: same service is not identical overflow performance, and same effort is not equal hours or kilometers.

The simulator is fitted on all observations using the same model family as the planner. Policy thresholds are described as tuned to match outcomes on this evaluation period. Treat these runs as exploratory simulations, not independent counterfactual proof or an untouched final test. Evaluate tuning choices on an earlier validation window, then freeze them for a later test; repeat across random seeds and alternative demand assumptions.

## Corrections before presenting results

### P0: correct the notebook's interpretation

- **Remove the invented `overfull = 110%`.** The raw value gives no exact amount. Keep an explicit overflow flag and use censoring or a clearly labelled bound where a model needs it. The notebook's numerical means and rate/cluster features inherit this artificial value.
- **Do not detect collections from falling consecutive readings.** Under the project's pre-emptying interpretation, a reading belongs to a collection visit. The next reading is before another collection, after an intervening reset. A difference between those readings does not measure growth within one filling cycle.
- Consequently, the notebook's **4,266 detected emptyings**, its **44.4% late / 26.2% premature audit**, and growth rates based on positive differences are not a valid collection-efficiency benchmark. Audit the actual visit readings and estimate each interval under an explicit emptying/reset assumption.
- **Rebuild groups after correcting features.** The two-container cluster labelled chronic overflow is too small to support a confident operating tier without observation-count and uncertainty checks.
- Treat holiday explanations as hypotheses. Monthly fill at collection is confounded by when and how often collections occur. A plot alone does not establish a holiday-caused volume surge.

Confirm with the challenge mentor that each row represents a pre-emptying reading and that the relevant bin was emptied at that visit. The Python interval model depends on that assumption too.

### P0: make historical planning use only information available then

In [the Streamlit app](../../fillinq-router/app.py), `model = _model(iv, data_key)` fits all intervals before the selected planning day is considered. The planner later filters last observations to before the day, but this does not remove future information already used in training. Its state also includes containers first observed after the chosen historical date.

For a historical planning date, train on completed eligible intervals and build the known-bin inventory only from the historical prefix. Distinguish morning dispatch from an end-of-day historical view: same-day collection readings are not available before that morning's dispatch. The separate `forward_test` function already uses a chronological training split; this concern is about the interactive planner's path.

### P0: fix route feasibility and failed-service reporting

In [the route engine](../../fillinq-router/fillinq/routing.py):

1. `_solve` clips an individual site's volume and weight to vehicle capacity before solving. A site larger than a vehicle is therefore understated. Reject it with a clear reason or support explicit split pickups; do not silently reduce demand.
2. When the solver returns no solution, it returns every site as optional and an empty mandatory list. `plan_routes` can then stop increasing the fleet because it sees no unserved mandatory stops. Preserve mandatory status and return an explicit failure.
3. The engine enforces total volume and mass, but **not separate white/green/brown chamber capacities** or truck/bin compatibility. The research report and notebook propose these; the current solver has not implemented them.
4. A short heuristic search returns a feasible proposal when successful; it does not prove globally optimal routes or a minimum fleet.

In [the simulator](../../fillinq-router/fillinq/simulate.py), the baseline records all historical stops and empties all corresponding bins even if the router cannot serve them. The dynamic policy collects only bins at actually routed stops. Apply the same served-stop accounting to both sides before comparing fleet and service results.

The saved dynamic runs already report **50 and 121 dropped-mandatory stop-day occurrences**, respectively. These are summed daily counts, not counts of distinct sites. Show missed mandatory service beside savings; it cannot disappear from the headline assessment. Baseline dropped-mandatory counts are not recorded in its daily CSV.

### P1: connect the existing parts and align their inputs

The [Nuxt forecast page](../apps/web/app/features/system/components/ForecastIntegration.vue) still states that the model is not connected. Its current route preview is straight-line/manual planning, while the Python project contains the forecast and constrained solver. Choose one demonstration interface and connect it to those implementations rather than developing another model.

The 449 coordinates just applied to SQLite are **synthetic UUID-to-site assignments**. The Python router does not read that table; it currently loads an optional `site_locations.csv` or generates its own coordinates. Its saved routing results therefore do not use the newly applied geography.

Use one coordinate snapshot for the chosen demonstration, retain synthetic provenance when exporting it, and rerun routing comparisons. The Python CSV loader currently treats any complete supplied coordinate file as real, so simply exporting the synthetic positions must not relabel them as verified original sites. Even road routing over mapped sites cannot establish real historical savings while the UUID-to-site mapping is synthetic.

Also bind displayed evaluation results to the data/model/coordinate versions. The Streamlit app loads bundled saved metrics even when a different observation CSV is uploaded; those figures must not appear to evaluate the uploaded dataset.

## Fit to the challenge deliverables

| Deliverable in the brief | Current evidence | Remaining demonstration work |
| --- | --- | --- |
| Dataset upload and processing | Present in Streamlit; Nuxt uses read-only SQLite | Show a clear upload/validation path in the chosen interface. |
| Patterns, grouping and anomalies | Notebook, Streamlit and Nuxt analytics exist | Correct notebook semantics; show sparse-data uncertainty and avoid causal holiday claims. |
| Configurable operating variables | Python exposes density, bin volume, truck volume/payload, shift, service, depot and unloading settings | Keep assumptions visible; add chamber constraints and handle infeasibility honestly. |
| Automatic routes and fleet recommendation | OR-Tools implementation exists separately | Fix the identified edge cases and connect its outputs to the final interface. |
| Architecture and user guide | Python README, research PDF and Nuxt documentation exist | Explain the final connected implementation and its actual limitations consistently. |

## Recommended route to a convincing hackathon demo

1. Confirm the observation/emptying semantics; correct the notebook's unsupported audit numbers.
2. Reuse the Python rate model with a strict decision-date cutoff and per-bin uncertainty. Compare against the per-container baseline on chronological data.
3. Fix demand truncation, no-solution handling and baseline served-stop accounting. Test oversized stops, impossible shifts, unavailable fleet and compartment limits.
4. Connect forecast selection and routing to one interface using one explicitly synthetic coordinate snapshot.
5. Demonstrate one planning day: **upload/history → forecast and reasons for urgency → selected bins → routes, trucks, loads and unloading → missed-service warnings**. Change truck capacity or the risk threshold and show the resulting trade-off.
6. Present held-out forecast improvement and clearly labelled simulation outcomes. Lead with a quantified service/cost frontier rather than an unsupported promise of lower distance, fewer overflow events and fewer trucks simultaneously.

That scope addresses the actual challenge with existing work. A road-time matrix and confirmed operational inputs would strengthen the demonstration, but do not let production-scale features displace the correctness fixes and one complete end-to-end story.
