# Designer-inspired UI implementation

## Design references

Source folder: `idea of UI:UX/`.

- `circular_municipal_fleet/DESIGN.md`: industrial neutral surfaces, green actions, compact navigation, mono data labels, material colors, responsive layout.
- `planning_workspace_route_optimizer`: historical baseline, grouped location cards, fraction meters, map canvas, active-plan drawer.
- `bin_details_forecasts`: location metadata, separate glass-bin cards, historical readings, audit table.
- `collection_plan_export_manifest`: grouped stop sequence, reordering, notes, exports, printable collector sheet.
- `system_states_technical_specification`: loading, empty, unavailable, and error patterns.
- `project_prd_system_brief.md`: long-term product direction, not evidence that telemetry, forecasts, vehicle constraints, or operational integrations already exist.

The project remains named **Garbage Collector**. The implementation adopts the design language without implying a PreZero deployment or adding its fictitious sample records.

## Composition

```text
app.vue
├── WorkspaceSidebar
├── WorkspaceHeader
└── selected module
    ├── PlanningView
    │   ├── PlanningFilters
    │   ├── LocationClusterList
    │   │   └── LocationClusterCard
    │   │       └── HistoricalFillMeter
    │   └── PlanningMapPanel
    │       ├── BinMap.client
    │       └── RoutePlanDrawer
    ├── HistoryView
    │   └── HistoryTable
    ├── LocationDetails
    │   ├── BinFractionCard
    │   ├── HistoricalReadingsChart
    │   └── HistoryView
    ├── CollectionManifest
    │   ├── PlanMetrics
    │   ├── ManifestStopCard
    │   ├── BinMap.client
    │   └── ExportActions
    ├── CollectionAnalyticsView
    │   ├── MaterialAnalyticsTable
    │   └── MonthlyCollectionTable
    ├── ForecastIntegration
    └── SystemStatus
```

Shared `GlassFractionBadge` and `WorkspaceState` components provide consistent material labels and loading/error/empty states.

## Table interactions

Table behavior is isolated in feature state modules (`createHistoryFilters`, `createMaterialTable`, `createMonthlyTable`), with a shared `createTableSort` model and typed analytics column configuration. Vue table components render state and emit interactions.

History, material statistics, and monthly statistics share `UiSortableHeader` for native keyboard-accessible sort buttons and `aria-sort` direction. History sorts on the API before pagination and combines a partial location UUID search with exact-location, material, and inclusive date filters. Changing a filter or sort returns to page one. All history requests retain the planning cutoff.

Analytics uses the shared pure `sortTableRows` helper before pagination, without changing source data. Missing statistics sort last in both directions. Each analytics table can filter by glass fraction.

History's numeric fill sorting parses the matching manual records in memory using `RecordedFill`, so malformed readings remain unknown and overfull never becomes a percentage. Other history sort columns and all history filters execute in SQLite. If the dataset grows substantially, normalize recorded fill into typed database columns before moving this sort into SQL.

## State and boundaries

`features/workspace/model.ts` composes independent data, filter, plan, and navigation state; `features/planning/state` and `features/manifest/state` own their respective logic. `composables/useCollectionWorkspace.ts` supplies request-scoped Nuxt data sources and provides the model to child components through Vue injection. No module-level mutable user state is shared between server requests.

- The planning API receives the selected `asOf` cutoff.
- `features/inventory/domain/catalog.ts` rejects mismatched snapshots and later readings before deriving visible bins.
- A location card groups bins; its group checkbox affects only bins matching the active filters. Meters still show all known fractions at that location so a filtered-out fraction is not mislabeled as missing.
- Thresholds apply to historical pre-emptying readings. Unknown readings stay unknown and only match when the threshold is off (0%).
- Selection uses `(locationId, material)` keys. The manifest groups selected bins into location stops.
- Selected bins persist when switching modules. A date change clears selection, notes, inspection state, and manual order immediately.
- Moving stops changes map lines, distance, manifest order, and CSV export together. Nearest-neighbor ordering can be restored explicitly.
- CSV contains one row per selected bin, its observation date, fill percentage, and location; notes use CSV escaping.
- Printing uses the browser's print/PDF functionality and a print stylesheet. It does not claim an official signed dispatch document.
- SQLite remains read-only. Draft plans/notes live in memory and disappear on reload.

## Project-owned controls and visuals

The frontend no longer depends on Onyx. Fifteen reusable Vue controls live in `shared/ui/controls`: button, icon button, icon, card, tag, input, select, checkbox, segmented control, slider, textarea, table, pagination, information card, and loading indicator. They use semantic HTML, explicit labels, native disabled states, and shared focus styles. Native navigation buttons form a permanent icon rail without an overflow menu or expansion state.

`shared/ui/CollectionDatePicker.vue` implements the calendar popover. Pure helpers in `shared/domain/calendar.ts` own Monday-first month grids, inclusive bounds, initial visible date, and date/month movement. Selection emits a draft ISO service day; the existing calendar-footer Apply date action commits it. Optional history dates can clear, while planning dates remain required. Today never overrides database bounds. Arrow keys move between days; Escape closes the popover and restores focus.

`shared/domain/pagination.ts` produces a bounded set of page links and ellipses so large historical tables remain compact. Component tests compile the actual Vue SFCs and exercise their rendered native control behavior using Vue's renderer, without a browser or extra UI testing dependency.

Leaflet supplies maps and geospatial layers. Historical meters use semantic progress bars; observed-reading charts use SVG points and dated tooltips. Neither implies live sensors or forecasts.

CSS is split into theme/base/layout/responsive rules, control styles, shared domain visuals, and feature styles. The uploaded planner and detail designs guide the split canvas, material cards, typography hierarchy, white surfaces, and restrained green selections. System fonts keep the interface self-contained; no external font request is required.

## Intentional data limitations

| Design assumption | Current implementation |
| --- | --- |
| Street addresses and named districts | Existing location UUIDs; no invented addresses |
| Current sensor fill and battery status | Actual manually recorded pre-emptying readings |
| Continuous accumulation curves | Individual observed points only |
| Forecast curves and confidence | Clear integration-pending state |
| Weight, volume, truck capacity, ETAs | Omitted because the database does not contain them |
| Driver dispatch and fleet assignment | Explicitly not connected |
| Road-optimal routes | Straight-line preview with nearest-neighbor/manual order |
| Real municipal coordinates | Existing synthetic coordinates, labeled as such |
| Persisted plan synchronization | Draft in memory; CSV and print exports |
| Sensor pipeline health | Actual `/api/health` response and snapshot availability |

## Verification

Use `./scripts/test.sh` for all backend/frontend unit and service tests; use `pnpm --dir apps/web typecheck`, and `pnpm --dir apps/web build`.

The frontend suite covers routing and workspace transformations. Live click-through, map-tile access, responsive screenshots, and print output require a browser running outside the implementation environment's socket restrictions. These have not been visually verified here.

Historical analytics are calculated by `CollectionAnalytics` on the backend, using the same inclusive cutoff contract. Overflow flags remain separate from numeric fill values throughout the UI and CSV. Analytics tests cover distributions, denominators, intervals, empty groups, invalid cutoffs, and future-data isolation.

## File organization

Views and components now live beside their feature's models, adapters, and styles under `app/features/{planning,history,inventory,manifest,analytics,map,system}`. Shell components live in `app/components/layout`; stateless shared presentation is in `app/shared/ui`. The full workspace provider is internal; connected views consume data, navigation, filters, or collection-plan capabilities individually.

See [code structure and change guide](code-structure.md) for the dependency rules, exact file layout, and extension points.

The sidebar is a permanent 76px icon rail (60px on small screens). There is no expansion control or overflow menu. Buttons have accessible labels, native title tooltips, visible focus, and active-page indicators. Module navigation preserves selections until the planning cutoff changes.

### Redesign verification

The custom control and calendar regressions run with `pnpm --dir apps/web test`. Type checking and production build pass without an Onyx module or runtime dependency. Live browser screenshots and print review remain unverified because this environment prevents local socket binding. The visual source folder and its original mock data have not been modified.

See [theme and domain presentation](design-tokens.md) and the [updated designer component brief](../google-stitch-components.md).

Current frontend verification: **66 passing tests**, including compiled Vue control tests and calendar interaction tests. Calendar selection rejects dates outside the data horizon even if an event is dispatched programmatically. Tests preserve historical cutoff behavior and existing selection/export rules.

Planning dates use the calendar’s confirmation mode: selecting a day stages a local draft and keeps the popover open. Apply date in the calendar footer commits it; Cancel, Escape, or an outside click leave the active cutoff unchanged. Reopening discards an unapplied draft. Optional history pickers retain immediate selection. Component regressions cover applying and cancelling.

Historical context now uses a single compact “Locked” indicator with a lock icon at the top right of the global header. Its tooltip identifies the cutoff and exclusion of later records. Per-module historical-cutoff banners have been removed. The indicator remains visible on small screens.
