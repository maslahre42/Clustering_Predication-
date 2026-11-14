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
| Planner filters and location cards | `features/planning/state/createPlanningFilters.ts`, `features/planning/components/` | `planning.test.mjs`, `workspace.test.mjs` |
| History filtering, search, requests | `features/history/state/createHistoryFilters.ts`, `features/history/composables/useHistoryQuery.ts`, `HistoryView.vue` in that feature's `components/` | `history-filters.test.mjs`, `table-components.test.mjs` |
| History table and API ordering | `features/history/components/HistoryTable.vue`; backend `Features/History/` (see below) | `table-components.test.mjs`, API `History/History*Tests.cs` |
| Shared sort behavior | `shared/state/createTableSort.ts`, `shared/domain/table.ts`, `shared/ui/controls/UiSortableHeader.vue` | `table-state.test.mjs`, `table-sorting.test.mjs` |
| Analytics tables | `features/analytics/state/`, `config/tableColumns.ts`, `components/*Table.vue` | `table-state.test.mjs`, `table-components.test.mjs` |
| Forecast, selection, routes (proposal) | `features/proposal/` (`domain/`, `state/`, `components/`), `shared/api/contracts/proposal.ts`; backend `Features/Proposal/` (see below) | `proposal-*.test.mjs`; API `Proposal/*Tests.cs` |
| Combined Python engine, forecast curves, simulation | `forecast_service/worker.py`, `forecast_service/integrations/{dataset,comparison}.py`, `forecast_service/integrations/{kaise,zakaria}/`, `../Omar-Work/fillinq/`; backend `Features/Proposal/PythonForecastEngine.cs`, `ProposalEndpoints.cs`; web `features/proposal/components/ForecastAnalysis.vue`, `ForecastExplorer.vue`, `SimulationResults.vue`, `state/createAnalysisState.ts`, `shared/api/contracts/simulation.ts` | `forecast_service/tests/`, `../Omar-Work/tests/`, `proposal-analysis.test.mjs`, `proposal-view.test.mjs`, API `ProposalEndpointTests.cs`, `SimulationRulesTests.cs` |
| CSV analysis dataset, grouping and three-project validation | Web `features/proposal/state/createProposalDataset.ts`, `components/ProposalDataEvidence.vue`, `ProjectValidationResults.vue`, `CollectionProposalView.vue`, `shared/api/contracts/comparison.ts`; Python `integrations/` | `proposal-dataset.test.mjs`, `proposal-analysis.test.mjs`, `proposal-view.test.mjs`, `forecast_service/tests/test_combined.py`, API `ProposalEndpointTests.cs` |
| Analytics metrics and loading | `features/analytics/composables/useHistoricalAnalytics.ts`, `components/`; backend `Features/Analytics/` | API `Analytics/CollectionAnalyticsTests.cs` |
| Bin identity, joins, location details | `features/inventory/domain/catalog.ts`, `types.ts`, `components/` | `workspace.test.mjs`, `coordinates.test.mjs` |
| Fill labels, material icons | `shared/domain/fill.ts`, `shared/ui/HistoricalFillMeter.vue`, `GlassFractionBadge.vue`, `icons.ts`, `styles.css` | `historical-fill-states.test.mjs`; API `Domain/RecordedFillTests.cs` |
| Map provider, markers, route lines | `features/map/basemap.ts`, `components/BinMap.client.vue`, `styles.css` | `basemap.test.mjs`; visual check |
| Route selection, order, distances | `features/manifest/state/createCollectionPlan.ts`, `shared/domain/geometry.ts`, `shared/config/workspace.ts` | `workspace-state.test.mjs`, `workspace.test.mjs` |
| Manifest, notes, CSV, printing | `features/manifest/components/`, `domain/planExport.ts`, `shared/browser/` | `print-document.test.mjs`, `download.test.mjs`, `workspace.test.mjs` |
| API URLs, DTOs, web proxy | `shared/api/routes.ts`, `shared/api/contracts/`, `apps/web/server/api/[...path].ts` | Request-binding tests + typecheck |
| SQLite mapping and connection | Backend `Infrastructure/Persistence/` | API relational tests |
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
