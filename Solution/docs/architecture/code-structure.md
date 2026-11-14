# Code structure and change guide

Start with the task-oriented [code index](../../CODE_INDEX.md) for a focused change. This document explains boundaries in more detail.

The application remains one ASP.NET Core backend and one Nuxt frontend. The refactor introduces feature boundaries and explicit adapters rather than extra services, generic repositories, or a new state-management dependency.

## Backend

`/api/data-range` reads global observation bounds for date navigation. `features/workspace/planningDate.ts` validates selections and defaults out-of-range initial dates to the latest observation. This metadata is independent of cutoff-filtered historical results.

```text
apps/api/
  Program.cs                         # Composition root
  Api/EndpointRegistration.cs         # Registers HTTP endpoints
  Domain/
    Collections/
      Observation.cs                 # Source observation entity
      HistoricalCutoff.cs            # Valid inclusive service-day boundary
      RecordedFill.cs                # Numeric / overfull / unknown semantics
    Locations/BinLocation.cs
  Features/
    Dataset/                         # Global planning navigation date bounds (+ 7 days)
    History/                         # Request/response contracts, validation, reader, endpoints
    Planning/                        # Cutoff-safe latest-bin snapshots and endpoints
    Analytics/                       # Historical statistics and endpoints
    Locations/                       # Coordinate metadata endpoint
  Infrastructure/Persistence/
    HistoryDbContext.cs              # Existing table mappings
    ObservationQueries.cs            # SQL-translatable cutoff filter
    PersistenceRegistration.cs       # Read-only connection configuration
```

Domain code does not depend on EF, HTTP, or other feature modules. Feature computations use the shared cutoff and fill rules. EF access is explicit in readers/endpoints; there is no generic repository hiding SQL behavior. Endpoint paths and JSON shapes remain compatible.

`Program.cs` wires the application together. Normal startup still opens the source SQLite database read-only and does not migrate or seed it. Tests use separate in-memory SQLite connections.

## Frontend

```text
apps/web/app/
  app.vue                            # Shell and lazy module composition
  components/layout/                 # Workspace header and navigation
  composables/useCollectionWorkspace.ts
  features/
    workspace/model.ts               # Composes feature models per request
    planning/
      components/                    # Planner, filters, location list, route drawer
      state/createPlanningFilters.ts
      styles.css
    manifest/
      components/                    # Manifest, stop cards, metrics and export controls
      state/createCollectionPlan.ts
      domain/planExport.ts
      styles.css
    history/
      components/                    # Audit view, table, readings chart
      composables/useHistoryQuery.ts
      state/createHistoryFilters.ts
      styles.css
    inventory/
      components/                    # Location details, profile and bin cards
      domain/catalog.ts              # Eligible bin joins and physical-stop grouping
      types.ts                       # Frontend bin model, distinct from API DTOs
      styles.css
    analytics/
      components/                    # Summary, material/month tables, distribution panel
      composables/useHistoricalAnalytics.ts
      state/                         # Material/month table filters, sorting and paging
      config/tableColumns.ts         # Typed table column definitions
      styles.css
    map/components/BinMap.client.vue
    system/components/               # Connection status and forecast integration state
  shared/
    api/contracts/                   # Separate history/planning/analytics/location DTOs
    api/routes.ts                    # API resource names and paths; also used by proxy allowlist
    domain/                          # Dates, fill presentation, geometry, coordinate provenance
    state/createTableSort.ts         # Atomic field/direction updates; shared by tables
    config/                          # Material vocabulary and injectable preview depot
    browser/download.ts              # Browser download side effect
    ui/                              # Shared domain presentation and project-owned native Vue controls
  assets/
    main.css                         # Ordered CSS entrypoint
    styles/                          # Theme tokens, base styles, layout, responsive rules
```

History reads are orchestrated by `HistoryReader`. `HistoryQuery` owns SQL filters and date/location/material ordering; `HistoryFillOrdering` orders parsed readings without inventing overflow percentages. Endpoint binding and reader logic both validate queries.

### State and dependency direction

`features/workspace/model.ts` composes:

- `data`: ready state, eligible bins, grouped locations, map metadata.
- `filters`: search, fraction/threshold filters, sorting, filter reset.
- `plan`: individual selection, grouped stops, notes, manual order, depot and geographic distance.
- `navigation`: active module and inspected location.

The composition owns the cross-feature rule that a date change clears the draft immediately. Feature models use Vue reactivity but have no Nuxt globals, HTTP calls, or browser effects. They can be instantiated directly in Node tests.

`composables/useCollectionWorkspace.ts` supplies Nuxt requests, handles browser export, and provides a request-local workspace. Connected views consume narrower capabilities through `useWorkspaceData`, `usePlanningFilters`, `useCollectionPlan`, and `useWorkspaceNavigation`. Reading one of these never creates another fetch or workspace.

Shared UI receives props and emits events. It must not inject workspace state or import a feature implementation. Feature-specific connected containers may use their feature models/adapters. Shared domain functions must not import feature code; feature models may use shared primitives and explicit inventory types.

Nuxt registers each feature's component directory explicitly with `pathPrefix: false`, preserving descriptive component names such as `PlanningMapPanel`. Use unique names; do not introduce two global `DetailsCard` components. Secondary module views use lazy imports.

### Data queries

- Workspace snapshot/location/health requests are in the workspace adapter.
- History filters and page-reset rules live in `createHistoryFilters`; the HTTP wrapper is `useHistoryQuery`.
- Location charts use the same feature's `useLocationHistory` adapter.
- Analytics loading and cutoff matching live in `useHistoricalAnalytics`.
- Analytics table behavior lives in `createMaterialTable` and `createMonthlyTable`; table columns live in `config/tableColumns.ts`.
- Shared `createTableSort` updates field and direction together and exposes read-only computed values to components.
- `shared/api/routes.ts` contains the resource names used by the UI and server proxy. The proxy still accepts only known GET resources.

Do not build API URLs, repeat raw fill parsing, or add persistence writes inside a presentation component.

### Styling

Global rules are limited to shared tokens, base typography, shell/layout, reusable UI, and responsive/print behavior. Feature styles live with their feature and use domain-specific class names. Project-owned controls in `shared/ui/controls` use native HTML semantics and shared CSS. `CollectionDatePicker` owns calendar interaction; its UTC service-day grid and bounded navigation are isolated in `shared/domain/calendar.ts`.

`assets/main.css` preserves an explicit import order, with responsive/print rules last. Keep layout changes out of domain/state files. The shell fits the dynamic viewport; `#workspace-content` owns page scrolling while the header, sidebar, and footer remain within the shell. Print rules restore normal document flow and visible overflow so long manifests are not clipped.

## Common changes

| Change | Primary files |
| --- | --- |
| Add a planning filter | `features/planning/state/createPlanningFilters.ts`, `PlanningFilters.vue`, state regression tests |
| Change API transport or endpoints | `shared/api/routes.ts`, API contracts, feature query adapters, Nuxt server proxy |
| Change overflow semantics | Backend `Domain/Collections/RecordedFill.cs`, shared frontend `domain/fill.ts`, corresponding tests |
| Change cutoff policy | Backend `HistoricalCutoff.cs` and query/snapshot tests; frontend date/state/query tests |
| Change depot default or inject another depot | `shared/config/workspace.ts`; optional configuration argument to `createWorkspaceModel` |
| Replace route ordering | `features/manifest/state/createCollectionPlan.ts` and geometry/service adapter; keep UI contracts stable |
| Add saved plans | Add an explicit persistence adapter and backend feature; preserve date/reset rules and source provenance |
| Add real coordinates | Controlled import plus `isSynthetic`; bin joins, stops, map and CSV now preserve the actual flag |
| Change metrics layout | `shared/ui/MetricCard.vue`; feature summary components supply values |
| Change history requests | `features/history/state/createHistoryFilters.ts` and `composables/useHistoryQuery.ts` |
| Add a backend feature | Add its own folder, endpoint registration, contracts/domain logic and tests |

Coordinate import itself is not implemented. The refactor removes the old hardcoded synthetic flag in derived map and CSV data, so a verified real mapping is no longer relabeled synthetic by those transformations. The preview depot remains synthetic by default and no operational road routing has been added.

## Tests and preserved behavior

Use `make setup` on a fresh checkout, then `make test` for backend and frontend tests (`./scripts/test.sh` remains available). `make check` also runs type checking and builds. The Makefile wraps existing commands; it owns no application logic. `tests/makefile.test.mjs` covers command dispatch, failure propagation, configurable paths, and database-preserving cleanup. Current verified result: **93 API + 6 AppHost + 86 frontend/tooling = 185 passing tests**. New regression cases cover shared domain rules, history-query resets, coordinate metadata, browser download cleanup, injected depots, and request-local workspace isolation.

Vue interaction test infrastructure lives in `tests/helpers/vue.mjs`. Primitive/calendar scenarios are in `ui-controls.test.mjs`; table wiring is in `table-components.test.mjs`; pure table state is in `table-state.test.mjs`. The helper resolves imports from the original component source rather than injecting mocked application logic.

Run `pnpm --dir apps/web typecheck` and `pnpm --dir apps/web build` after relevant frontend changes. Both pass after this refactor. NuGet can still emit an audit-feed availability warning; auditing has not been disabled.

Every logic change must include unit/regression tests in the same change. Do not replace behavioral assertions with tests that merely check file locations. Source observations, database schema, REST paths, cutoff semantics, and the current route-preview workflow are preserved. Browser click-through and responsive/print screenshots remain unverified in this socket-restricted environment.

## Optional local orchestration

`apps/apphost` adds an Aspire composition root for the API and pnpm/Nuxt development process. It supplies the runtime backend endpoint, forwards the SQLite path override, and waits for database health before starting the frontend. Application features remain independent of Aspire. Resource-graph tests live in `tests/GarbageCollector.AppHost.Tests` and run with the existing xUnit runner. See [Aspire configuration and diagnostic scope](aspire.md).
