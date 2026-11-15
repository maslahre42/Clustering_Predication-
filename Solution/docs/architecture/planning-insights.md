# Compartments, costs, timing and scenario evidence

The live proposal uses `forecast_service/integrations/planning_insights.py` for cost arithmetic and time-to-full explanations. `OperationsSettings.cs` owns HTTP validation; web `domain/settings.ts` mirrors the editable contract. All new rates/capacities default to zero: unpriced or unknown, not an invented equal split.

## Physical capacity

Enter all three actual chamber volumes together, each at least one litre. Their sum cannot exceed a known total truck volume. The effective aggregate limit is their sum or the smaller configured total, with the payload limit still enforced. `fillinq/routing.py` aggregates each selected material independently and adds three capacity dimensions. All chambers can reset only at the shared disposal node. A pickup stays indivisible; an oversized colour is explicitly unserved. Missing, negative, inconsistent or nonfinite material demand cannot be routed under configured chambers.

The same material demand and capacities reach historical/Omar/Zakaria policy replay and the bounded one-load Gurobi validation sample. Each exported proposal load includes its forecast colour volumes. The UI shows these beside configured capacities. The layout is shared by the available fleet; individual heterogeneous trucks are not modelled.

## Operating costs

`road km × variable EUR/km + scheduled truck shifts × fixed EUR/shift`. Only trucks with served collections count; multiple unloading loads do not create extra fixed charges. Replay counts actual truck-days. Decimal arithmetic rounds each cost category to cents, then sums those displayed categories. Both rates zero means unpriced, not a free operation. One rate zero is explicitly a partial estimate. A positive distance rate without street distance cannot yield a total. These prices explain plans; the routing objective remains road distance with hard service/capacity/shift constraints.

## Time until full

The existing cutoff-fitted Omar model supplies 10%, median and 90% time-to-full quantiles. These use its reset-month seasonal approximation, not a new validated time estimator. The table subtracts elapsed days at the inclusive cutoff. Negative days remain visible as past the model estimate. The estimated full date is the median rounded up to a calendar day. Unknown observations reset the date but provide no rate. A container without its own completed rate-bearing cycle has an explicit unavailable estimate, even if pooled rates can support risk forecasts. Estimates outside ten years or nonfinite values are unavailable. These uncalibrated intervals are not service guarantees or dispatch dates.

## Scenario and presentation state

`state/createScenarioComparison.ts` owns a deep copied baseline in the proposal parent, surviving the next proposal request. Cutoff/dataset changes clear it immediately. Draft edits hide comparisons and disable saving/presentation. `domain/insights.ts` permits a distance/cost reduction only for matching dataset fingerprints and dates, identical collected location/material pairs, no missed urgent sites, matching road sources, prices, and physical/service assumptions. Fleet, payload, chamber, shift and selection changes can be explored, while unequal completed service is labelled a trade-off. Negative reductions indicate increases; all comparisons are modelled, not measured savings.

`PlanPresentation.vue` displays six slides from the current calculated plan and optional baseline. A native modal dialog traps focus, supports Escape and arrow navigation, and closes on input/proposal changes. The map, timing, costs and scenario views share the same actual proposal data. Final hand-off uses the existing route CSV and accepted manifest. No invented benchmark or savings percentage is displayed.

## Verification

Regression tests: `forecast_service/tests/test_planning_insights.py`, `tests/proposal-insights.test.mjs`, API `OperationsSettingsTests.cs` and `ProposalEndpointTests.cs`. They cover capacity resets, missing/oversized composition, simulated-policy and Gurobi constraints, decimal/unpriced costs, cutoff invariance, unknown resets, sparse/overdue timing, draft handling, baseline invalidation, matched service, presentation navigation and export. Build/runtime verification is recorded in the handover guide.

Executed verification: 407 distinct tests passed (211 API, 6 AppHost, 141 frontend/tooling, 49 Python), plus type checking and production builds. Live browser checks used the original data through 2026-09-30 and tested 1,338 timing rows, request binding for 8/10/12 m³ chambers, per-load chamber and payload limits, road-based cost arithmetic, baseline survival across recalculation, stale-draft blocking, all six slides, native modal focus, search-input arrow keys, mobile bounds, CSV download, Escape and accepted-manifest costs. No browser page errors occurred.

With test prices of €1.20/km and €150/truck shift, the 12 t plan cost €3,748.86 with three missed urgent sites; reducing payload to 10 t cost €3,728.57 with four missed urgent sites. The app correctly withheld a savings claim because completed service differed and both plans missed urgent service. These are illustrative test scenarios, not an operational recommendation or measured savings. Original SQLite content remained unchanged.
