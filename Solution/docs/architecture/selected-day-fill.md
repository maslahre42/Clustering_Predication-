# Selected-day fill after recorded emptyings

The planning map previously displayed the latest **pre-emptying** reading on every later date. A bin found full on 30 September therefore still appeared full on 1 October, even though its recorded collection had reset it. The immutable historical snapshot remains valid as evidence of what was found; it is not current occupancy.

## Calculation and API

`GET /api/fill-state?asOf=YYYY-MM-DD` passes only observations through the inclusive cutoff to the request-local worker's `state` action. It returns one state per known location/material, `lastEmptied`, elapsed days, expected fill and 10–90% model quantiles. It uses the existing seasonal cycle model and needs no street-service requests. It is scoped to the original workspace dataset; uploaded proposal datasets remain separate.

A visit on the selected date yields a modeled zero after emptying, including a visit whose pre-emptying percentage was unknown. This is the same complete-emptying assumption used by the forecast; no measured post-emptying residual is available. On following days the model estimates accumulation from the last visit. Sparse bins can borrow known same-material rates; when neither a fitted model nor the material's rate is available the state remains unknown. Nonfinite/unsupported predictions are unavailable. Explicit overfull remains a historical category and is never copied into selected-day state or converted to 110%.

The response declares `semantics: after-recorded-emptyings`. The snapshot is after recorded visits on that calendar day, not morning dispatch or live telemetry; source dates have no visit times. Model bands are uncalibrated. When the selected date exceeds the last available observation, the UI identifies the missing subsequent collection records and projects only the known history. Advancing a date or accepting a proposed route does not mark bins emptied. A recorded visit is required for a reset.

## Frontend separation

`features/planning/domain/fillView.ts` overlays a selected-day display without mutating `lastFillPercent`, `lastIsOverfull`, `lastCollection` or source observations. The default view is **Selected-day estimate**, starting with a 50% minimum fill filter; Reset filters restores 50%. Recorded-only consumers without estimated-state input keep their unfiltered historical default. The view shows `0% · emptied` on a recorded collection date and `~x%` for subsequent estimates. **Last recorded before emptying** restores the original measurement/category and date. Planner cards and location details share this overlay.

`createPlanningFilters.ts` applies fill thresholds and sorting to the active display. Historical overfull ranks above numeric 100 only in recorded mode. Material identity remains separate. Mode changes reset location pagination, while existing selections remain explicit. Date changes retain the existing immediate clearing of drafts and reject old snapshot/state dates. Original history, analytics and historical CSV fields retain their original readings.

The adapter fetches fill state independently of the historical snapshot. A pending, failed, wrong-cutoff, wrong-reset-date or unavailable estimate never falls back to yesterday's full reading and never becomes a fabricated zero. Failed estimates remain unknown; the recorded view stays available, and Retry estimates refreshes the requests. Current percentages are forecasts, not new observations. The slider's accessible value text follows its active estimated/recorded meaning.

## Verification

Regression coverage includes full/overfull resets, 30 September → 1 October refill, unknown pre-emptying readings, sparse material borrowing, absent material rates, empty history, future-row invariance, no reset without a visit, active-view filters/sorting, separate material identities, stale/loading/error guards, immutable export evidence, mode-change pagination, labels and the actual view selector. HTTP binding tests verify inclusive source cutoff, date validation and unavailable/rejected engine responses. The relocated worker regression also exercises the new state action without sibling source projects.

All 432 tests passed (216 API, 6 AppHost, 151 frontend/tooling, 59 Python), plus type checking and production builds. Live browser verification used the actual dataset: a white bin found at 100% on 30 September showed zero after that visit, approximately 7.4% on 1 October and 14.9% on 2 October. Both bins whose final 30 September reading was numeric 100 were checked. Recorded mode retained 100%. Thresholds and details agreed; simulated request failure produced unknown fill, recorded evidence remained usable, and Retry recovered estimates. Mobile bounds passed, no page JavaScript errors occurred, and SQLite remained unchanged.

Startup/reset threshold regression tests cover 49.9% versus the inclusive 50% boundary, unavailable estimates, reset defaults, the accessible slider label, and progress while estimates are pending. Browser verification checks 50% on a fresh load, after Reset filters and after reload, plus mobile bounds.
