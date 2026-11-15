# Code index

Use the matching row, then read only the listed files and their direct dependencies. Frontend paths below are relative to `apps/web/app/`; backend paths are relative to `apps/api/`. Tests are under `tests/`.

## Find the change

| Task | Source entrypoints | Relevant tests |
| --- | --- | --- |
| Shell, sidebar, header, scroll bounds | `app.vue`, `components/layout/`, `assets/styles/base.css`, `assets/styles/layout.css`, `assets/styles/responsive.css` | Typecheck/build; visual check |
| Theme, colors, spacing | `assets/styles/tokens.css`, `assets/main.css`; feature `styles.css` | Visual check |
| Buttons, inputs, tables | `shared/ui/controls/` (one native control per component) | `ui-controls.test.mjs`, `table-components.test.mjs` |
| Calendar UI and navigation | `shared/ui/CollectionDatePicker.vue`, `shared/domain/calendar.ts` | `ui-controls.test.mjs`, `calendar-*.test.mjs` |
| Planning date bounds | `features/workspace/planningDate.ts`; backend `Features/Dataset/` | `planning-date.test.mjs`, API `History/DatasetDateRangeTests.cs` |
| Workspace ownership and resets | `features/workspace/model.ts`, `composables/useCollectionWorkspace.ts` | `workspace-state.test.mjs`, `workspace.test.mjs` |
| Selected-day fill after emptying, historical toggle and state requests | `forecast_service/worker.py::selected_day_state`, backend `Features/Proposal/ProposalEndpoints.cs` (`/api/fill-state`); `features/planning/domain/fillView.ts`, `state/createPlanningFilters.ts`, `components/PlanningFillMeter.vue`, workspace sources and inventory cards; [semantics](docs/architecture/selected-day-fill.md) | `forecast_service/tests/test_selected_day_state.py`, `test_standalone.py`, `selected-day-fill.test.mjs`, API `ProposalEndpointTests.cs` |
| Planner filters and location cards | `features/planning/state/createPlanningFilters.ts`, `features/planning/components/` | `planning.test.mjs`, `workspace.test.mjs` |
| History filtering, search, requests | `features/history/state/createHistoryFilters.ts`, `features/history/composables/useHistoryQuery.ts`, `HistoryView.vue` in that feature's `components/` | `history-filters.test.mjs`, `table-components.test.mjs` |
| History table and API ordering | `features/history/components/HistoryTable.vue`; backend `Features/History/` (see below) | `table-components.test.mjs`, API `History/History*Tests.cs` |
| Shared sort behavior | `shared/state/createTableSort.ts`, `shared/domain/table.ts`, `shared/ui/controls/UiSortableHeader.vue` | `table-state.test.mjs`, `table-sorting.test.mjs` |
| Analytics tables | `features/analytics/state/`, `config/tableColumns.ts`, `components/*Table.vue` | `table-state.test.mjs`, `table-components.test.mjs` |
| Reviews of new contributor uploads | `docs/kaise-new-code-review.md`, `docs/zakaria-new-code-review.md` (snapshot comparisons, reproduced evidence and adoption recommendations) | Contributor audit tests and isolated review probes; no app changes implied |
| Forecast, selection, routes (proposal) | `features/proposal/` (`domain/`, `state/`, `components/`), `shared/api/contracts/proposal.ts`; backend `Features/Proposal/` (see below) | `proposal-*.test.mjs`; API `Proposal/*Tests.cs` |
| Combined Python engine, forecast curves, simulation | `forecast_service/worker.py`, `forecast_service/integrations/{dataset,comparison}.py`, `forecast_service/integrations/{kaise,zakaria}/`, `forecast_service/vendor/fillinq/`; backend `Features/Proposal/PythonForecastEngine.cs`, `ProposalEndpoints.cs`; web `features/proposal/components/ForecastAnalysis.vue`, `ForecastExplorer.vue`, `SimulationResults.vue`, `state/createAnalysisState.ts`, `shared/api/contracts/simulation.ts` | `forecast_service/tests/`, `forecast_service/tests/engine/`, `proposal-analysis.test.mjs`, `proposal-view.test.mjs`, API `ProposalEndpointTests.cs`, `SimulationRulesTests.cs` |
| Data & imports page, CSV drag/drop, validation and active source | `features/system/components/SystemStatus.vue`, `features/system/styles.css`, `features/proposal/state/createProposalDataset.ts`, workspace dataset watcher; API `Features/Dataset/DatasetEndpoints.cs`, worker action `dataset`; [workflow](docs/architecture/data-imports.md) | `data-import-page.test.mjs`, `proposal-dataset.test.mjs`, `workspace-state.test.mjs`, `test_dataset_validation.py`, `test_standalone.py`, API endpoint tests; browser file-picker/drop/mobile |
| CSV analysis dataset, grouping and three-project validation | Web `features/proposal/state/createProposalDataset.ts`, `components/ProposalDataEvidence.vue`, `ProjectValidationResults.vue`, `CollectionProposalView.vue`, `shared/api/contracts/comparison.ts`; Python `integrations/` | `proposal-dataset.test.mjs`, `proposal-analysis.test.mjs`, `proposal-view.test.mjs`, `forecast_service/tests/test_combined.py`, API `ProposalEndpointTests.cs` |
| Analytics metrics and loading | `features/analytics/composables/useHistoricalAnalytics.ts`, `components/`; backend `Features/Analytics/` | API `Analytics/CollectionAnalyticsTests.cs` |
| Four monthly comparison charts (collections, active days, mean fill, full/premature shares) | `features/analytics/components/MonthlyDashboard.vue`, `domain/monthlyDashboard.ts`; backend `Features/Analytics/CollectionAnalytics.cs` | `monthly-dashboard.test.mjs`, API `Analytics/CollectionAnalyticsTests.cs` |
| Historical cadence/rate histograms, projected filling-time curve and container rankings | Backend `Features/Analytics/CollectionDynamics.cs`, `CollectionPatterns.cs`; web `features/analytics/state/createCollectionDynamics.ts`, `components/CollectionDynamicsPanel.vue`; [method](docs/architecture/collection-dynamics.md) | API `Analytics/CollectionDynamicsTests.cs`, `collection-dynamics.test.mjs`; live analytics check |
| Monthly pattern charts, partial periods, cycle rates and review flags | `features/analytics/domain/patterns.ts`, `state/createPatternTrends.ts`, `components/CollectionPattern*.vue`, `MonthlyCollectionTable.vue`; backend `Features/Analytics/CollectionPatterns.cs` | `analytics-patterns.test.mjs`, `table-components.test.mjs`, API `Analytics/CollectionPatternsTests.cs` |
| Bin identity, joins, location details | `features/inventory/domain/catalog.ts`, `types.ts`, `components/` | `workspace.test.mjs`, `coordinates.test.mjs` |
| Fill labels, material icons | `shared/domain/fill.ts`, `shared/ui/HistoricalFillMeter.vue`, `GlassFractionBadge.vue`, `icons.ts`, `styles.css` | `historical-fill-states.test.mjs`; API `Domain/RecordedFillTests.cs` |
| Map provider, markers, route lines | `features/map/basemap.ts`, `components/BinMap.client.vue`, `styles.css` | `basemap.test.mjs`; visual check |
| Optimized fleet map, truck/load filters and stop inspection | `features/proposal/domain/routeMap.ts`, `state/createRouteMapState.ts`, `components/ProposalRouteMap.vue`, `ProposalLeafletMap.client.vue`; proposal and manifest containers | `proposal-map.test.mjs`; browser map check |
| Street-distance optimization, road geometry and compact truck sectors | `forecast_service/vendor/fillinq/{roads,territories,routing}.py`; `forecast_service/worker.py`; `features/proposal/domain/settings.ts`, `components/ProposalSettingsForm.vue`, `CollectionProposalView.vue` | `forecast_service/tests/engine/test_roads.py`, `forecast_service/tests/`, `proposal-settings.test.mjs`, `proposal-map.test.mjs`; live road provider check |
| Automatic joint inventory, frequency and daily route recommendation | Python `integrations/joint_planning.py`, worker `capacity` automatic mode; API `CapacityPlanning.cs`; web `state/createCapacityPlanning.ts`, `state/createJointResults.ts`, `components/JointPlanningResults.vue`, capacity contracts and route-map input subset; [algorithm](docs/architecture/joint-planning.md) | `test_joint_planning.py`, `test_standalone.py`, `capacity-planning.test.mjs`, `proposal-map.test.mjs`, API endpoint binding; full-data API and browser |
| Physical containers per site, emptying intervals, filling-time averages and financial scenarios | API `Features/Proposal/CapacityPlanning.cs`, Python `integrations/capacity_planning.py`, worker action `capacity`; web `features/proposal/{domain/capacity.ts,state/createCapacityPlanning.ts,components/CapacityPlanning.vue,components/CapacityResults.vue}`, capacity contracts; [method](docs/architecture/capacity-planning.md) | `forecast_service/tests/test_capacity_planning.py`, `capacity-planning.test.mjs`, API `ProposalEndpointTests.cs`; live comparison/browser |
| Glass chambers, operating costs, time-to-full, scenario comparison and presentation | `forecast_service/integrations/planning_insights.py`, `forecast_service/vendor/fillinq/routing.py`, `integrations/zakaria/optimizer.py`; web `features/proposal/domain/insights.ts`, `state/createScenarioComparison.ts`, `components/{OperatingCosts,FillTimingTable,ScenarioComparison,PlanPresentation}.vue`; `OperationsSettings.cs` | `forecast_service/tests/test_planning_insights.py`, `proposal-insights.test.mjs`, API settings/endpoint tests; [rules](docs/architecture/planning-insights.md) |
| Active plan drawer auto-collapse and manual expansion | `features/planning/state/createPlanDrawerState.ts`, `components/RoutePlanDrawer.vue` | `plan-drawer.test.mjs`; browser first-add, clear, last-remove and mobile checks |
| Route selection, order, distances | `features/manifest/state/createCollectionPlan.ts`, `shared/domain/geometry.ts`, `shared/config/workspace.ts` | `workspace-state.test.mjs`, `workspace.test.mjs` |
| Manifest, notes, CSV, printing | `features/manifest/components/`, `domain/planExport.ts`, `shared/browser/` | `print-document.test.mjs`, `download.test.mjs`, `workspace.test.mjs` |
| API URLs, DTOs, web proxy | `shared/api/routes.ts`, `shared/api/contracts/`, `apps/web/server/api/[...path].ts` | Request-binding tests + typecheck |
| Karlsruhe demo coordinate replacement and provenance | `data/karlsruhe/`, `scripts/replace-location-coordinates.py`; [sources and backup](docs/karlsruhe-locations.md) | `forecast_service/tests/test_coordinate_replacement.py`; database history/schema/integrity verification |
| SQLite mapping and connection | Backend `Infrastructure/Persistence/` | API relational tests |
| Standalone relocation, bundled engine and Docker build context | `forecast_service/vendor/fillinq/`, `forecast_service/worker.py`, `apps/api/GarbageCollector.Api.csproj`, `apps/api/Dockerfile`, `apps/apphost/WorkspaceResources.cs`, `.gitignore`, `.dockerignore`; [handoff](docs/standalone-project.md) | `forecast_service/tests/test_standalone.py`, relocated `forecast_service/tests/engine/`, AppHost publish tests, `makefile.test.mjs`; isolated setup/check/publish/runtime |
| Make shortcuts / contributor commands | `Makefile`, `scripts/test.sh`, `README.md` | `makefile.test.mjs` |
| Local startup / Docker Compose | `apps/apphost/`, `docs/deployment/linux-compose.md` | `GarbageCollector.AppHost.Tests/WorkspaceResourcesTests.cs` |

## History backend ownership

- `HistoryEndpoints.cs`: HTTP parameter binding and validation responses.
- `HistoryContracts.cs`, `HistoryRules.cs`: DTOs, allowed query values, pagination bounds.
- `HistoryReader.cs`: database read orchestration, parsing, page response.
- `HistoryQuery.cs`: SQL filters, cutoff, and date/location/material ordering.
- `HistoryFillOrdering.cs`: parsed numeric/overfull/unknown ordering.
- `Domain/Collections/`: shared cutoff and fill rules; reused by planning/analytics.

## Proposal backend ownership

- `ProposalEndpoints.cs`: proposal, per-bin forecast and simulation endpoints, query binding and validation.
- `PythonForecastEngine.cs`: request-local JSON/stdin bridge to Omar's actual Python package, cancellation and time limit.
- `OperationsSettings.cs`: every operating number with its default, range checks, request overrides, collection calendar.
- `FillingCycles.cs`: visits → filling cycles (a visit empties the bin; full/overfull are lower bounds).
- `FillRateModel.cs`: tested C# reference model. Public forecasts use Omar's seasonal Python model through `forecast_service/worker.py`.
- `CollectionPolicy.cs`: one decision per bin (due, neighbour, optional, skipped, no forecast) and site stops with weight/volume.
- `RoutePlanner.cs`: tested C# reference heuristic. Public routing uses Omar's repaired OR-Tools engine.
- `CollectionProposal.cs`: C# reference composition. See [live Python integration and simulation](docs/architecture/proposal.md).

## Checks and runtime

`make help` lists shortcuts. First checkout: `make setup`, then `make run`. Use `make test` for all tests or `make check` for tests, type checking, and builds. The underlying commands remain available:

```sh
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
pnpm --dir apps/web build
./scripts/test.sh
```

Run one frontend test: `node --experimental-strip-types --test tests/history-filters.test.mjs` (replace filename). `tests/helpers/vue.mjs` compiles actual Vue components for interaction tests. API tests use isolated in-memory SQLite. The test runner also supports environments where VSTest sockets are unavailable.

Start/restart the full local app: `dotnet run --project apps/apphost`. API changes do not hot-reload under plain `dotnet run`; stop/restart the host. Nuxt development changes refresh automatically.

Further detail: [architecture](docs/architecture/code-structure.md), [UI composition](docs/architecture/ui-components.md), [product/domain rules](PROJECT_IDEA.md), [deployment](docs/deployment/linux-compose.md). Read those selectively.
