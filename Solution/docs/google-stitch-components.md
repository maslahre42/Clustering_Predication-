# Google Stitch prompt: Vue components and their purpose

Paste this brief into Google Stitch and attach screenshots of the current application.

---

## Design task

Redesign **Garbage Collector**, our existing Nuxt/Vue application for municipal glass-collection planning in Heilbronn. Use a PreZero-inspired visual direction: green accents, white surfaces, clear typography, compact controls, and accessible contrast.

Design reusable components, then compose them into complete screens. Use the Vue names below in design annotations so developers can map your designs to the code. Component names are not product labels.

Our controls are **project-owned Vue components using native HTML**, styled after the uploaded `idea of UI:UX` references. The Onyx library has been removed. Preserve accessible interactions. Leaflet/OpenStreetMap supplies the map. Custom semantic progress meters and an SVG chart display domain data.

## Essential product behavior

- Each location has separate brown, green, and white glass bins. A bin is identified by location plus material. Users select individual bins; selected bins at the same location form one collection stop.
- Readings are manually recorded **before emptying**. Historical percentages are not current fill levels. A high past reading does not establish current urgency.
- The selected planning date is an inclusive historical cutoff. Later observations must not affect visible bins, readings, or statistics.
- The planning picker allows the first database observation through seven days after the last. These bounds are dynamic. The additional seven days do not imply that forecasts exist.
- Applying a different date clears selected bins, inspected location, manual stop order, and draft notes. Switching modules at the same date preserves selections.
- Numeric percentage, **Overfull**, and **Unknown** are separate states. Never replace missing readings with zero or invent 110% for Overfull.
- Current coordinates and depot are synthetic. Preserve a discreet source indication. Do not invent street addresses from location UUIDs.
- Routes use nearest-neighbor or manual ordering and straight-line connections. Road routing, driving times, vehicle constraints, and verified optimization savings are not implemented.
- Forecasts are not connected. Plans and notes are drafts in memory. CSV and browser print/PDF are available.

## 1. Application shell

| Vue component | What it does | Design guidance |
| --- | --- | --- |
| `app.vue` | Composes sidebar, header, active module, and footer. Switches between planning, history, location details, analytics, forecasts, collection plan, and system status. | One consistent application shell, with room for dense data and a large map. |
| `WorkspaceHeader.vue` | Displays the green Garbage Collector title, planning-date field with an in-calendar Apply date action, and Locked indicator. Handles unavailable/loading date metadata. | Compact header. Keep the date label accessible but visually hidden. |
| `WorkspaceSidebar.vue` | Navigates between Route planner & map, Bin inventory & history, Historical analytics, Predictive forecasts, Collection plan, and System status. Always displays icons only. | Recycling icon, active states, and tooltips; no sidebar expansion control. Do not repeat the product name here. |

## 2. Planning workspace

| Vue component | What it does | Design guidance |
| --- | --- | --- |
| `PlanningView.vue` | Composes heading, filters, historical context, location list, and map. Handles loading/API errors. | Primary workflow: review locations → select bins → prepare a plan. |
| `PlanningFilters.vue` | Glass-material segmented filter, recorded-fill threshold slider in 5% steps, sorting by latest collection or highest fill, UUID search, and reset. | Group compact controls clearly. Describe the threshold as historical recorded fill. |
| `LocationClusterList.vue` | Shows matching locations in pages of 10 cards, with pagination and a no-results/reset state. | Scannable list beside the map. |
| `LocationClusterCard.vue` | Groups bins at a location. Shows short UUID, three material meters, group-selection checkbox, individual matching-bin checkboxes, and Inspect details action. Supports partial selection. | Distinguish inspected, hovered, and selected states. Group selection affects matching bins only; meters still show all known fractions. |
| `PlanningMapPanel.vue` | Combines map, coordinate-source context, depot/straight-line legend, and active-plan drawer. | Legible overlays that preserve space for markers and map controls. |
| `RoutePlanDrawer.vue` | Summarizes stops, bins, and straight-line round-trip distance; lists/removes stops; offers Review plan, Export CSV, Clear, and Add this day's collections. Collapses with a chevron. | Compact drawer with a contrasting icon toggle. Bulk-add means matching bins recorded on the selected day, not AI recommendations. |

## 3. Location details

| Vue component | What it does | Design guidance |
| --- | --- | --- |
| `LocationDetails.vue` | Combines location profile, three bin cards, reading chart, and historical audit. Offers Back to map and recovery states. | Hierarchy: location → glass bins → supporting history. |
| `LocationProfileCard.vue` | Shows coordinates, synthetic/imported source, known-bin count, unavailable capacity/road-access information, and small location map. | Compact identity/context card. Do not invent unavailable metadata. |
| `BinFractionCard.vue` | Represents one brown, green, or white glass bin. Shows latest recorded fill/date and history summary. Provides Select for plan/Remove from plan. Selection is disabled without eligible records. | One reusable pattern with material variants and selected, unknown, overfull, and unavailable states. |

## 4. History and observations

| Vue component | What it does | Design guidance |
| --- | --- | --- |
| `HistoryView.vue` | History panel with glass filter, From/To date pickers, reset, location context, and All locations action. Loads records respecting the planning cutoff. | Reusable in the main history module and location details. Consistent filter and recovery states. |
| `HistoryTable.vue` | Lists collection date, location UUID, glass fraction, and fill before emptying. Location links filter the audit. Sortable headers, partial UUID search, material/date filters, and pagination. | Readable compact rows, clear columns, and distinct numeric/overfull/unknown values. |
| `HistoricalReadingsChart.vue` | SVG scatter chart of individual numeric observations by date/material, with material legend and dated tooltips. | Observed points only. Do not turn them into continuous accumulation or forecast curves. Unknown/overfull readings are not fabricated numeric points. |

## 5. Collection plan and export

| Vue component | What it does | Design guidance |
| --- | --- | --- |
| `CollectionManifest.vue` | Full plan review: historical context, metrics, grouped stops, route map, exports, and empty-plan state. | Focused collector hand-off workspace that also prints well. |
| `PlanMetrics.vue` | Displays grouped stops, selected bins/material counts, straight-line closed-loop distance, and baseline date. | Consistent metric cards. Distance is not road mileage or travel time. |
| `ManifestStopCard.vue` | Numbered location stop containing selected materials, original reading dates/fill, Move up/Move down/Remove, Inspect history, and expandable collector notes. | Clear sequence and compact actions. Reordering updates map, distance, and export; notes remain drafts. |
| `ExportActions.vue` | CSV download, browser print/save as PDF, and restore nearest-neighbor order. Includes hand-off limitations and coordinate provenance. | Clear export hierarchy. Do not imply electronic dispatch, saved synchronization, or signed manifests. |

## 6. Historical analytics

| Vue component | What it does | Design guidance |
| --- | --- | --- |
| `CollectionAnalyticsView.vue` | Assembles summary metrics, fill distributions, material and monthly comparisons, historical context, and loading/error/empty states. | Descriptive analytics consistent with the planner. |
| `AnalyticsSummaryCards.vue` | Recorded collection count, overfull-at-collection count, known bins, and bins with fewer than three readings. | Sparse history is a coverage indicator, not forecast confidence. |
| `FillDistributionPanel.vue` | Per-material counts for 0–30%, above 30% below 70%, 70% below 100%, exactly 100%, Overfull, and Unknown. | Distinct categories. These do not prove whether collection was necessary. |
| `MaterialAnalyticsTable.vue` | Compares material collection counts, overfull readings, numeric mean fill, median collection interval, low readings, and unknowns; sortable columns and a glass filter. | Align numeric columns and show meaningful units/context. |
| `MonthlyCollectionTable.vue` | Month/material collection count, overfull count, and numeric mean fill; sortable columns, material filter, and pagination. | Preserve partial-month caveats at the chosen cutoff. |

## 7. Forecast and system screens

| Vue component | What it does | Design guidance |
| --- | --- | --- |
| `ForecastIntegration.vue` | Shows forecast-model integration pending and links to historical records. | An intentional pending state, without fabricated predictions or functioning forecast actions. |
| `SystemStatus.vue` | Actual API/database health, snapshot availability, eligible counts/date bounds, map/routing configuration, future integrations, and refresh. | Keep technical status here. This is application health, not live sensor or vehicle telemetry. |

## 8. Shared reusable presentation

| Vue component | What it does | Design guidance |
| --- | --- | --- |
| `CollectionDatePicker.vue` | A custom calendar for ISO service-day strings, with Monday-first month grids and keyboard navigation. Used by planning and history. Single selection with date bounds; optional fields can clear. | Design closed field and open calendar: navigation, selected/today/disabled days, keyboard focus, and unavailable state. Header label stays visually hidden. Preserve timezone-safe dates and min/max restrictions. |
| `GlassFractionBadge.vue` | Project-owned tag with recycling icon and brown/green/white glass label. | Reuse everywhere. Material color must not be confused with urgency. White glass must remain visible on white backgrounds. |
| `HistoricalFillMeter.vue` | Material-colored bin icon, material label, recorded percentage, and measurement date. Explicit Overfull/Unknown labels. | Plain background, no progress track; white glass uses a white bin with a visible outline. Never fake a numeric reading. |
| `MetricCard.vue` | Project-owned card with label, value, supporting caption, and compact variant. | Consistent metric language across analytics and planning. |
| `WorkspaceState.vue` | Loading indicator or information card for loading/error/empty/unavailable states, with optional recovery action. | Consistent recovery patterns, accessible alerts, and clear next steps. |

## 9. Shared map

| Vue component | What it does | Design guidance |
| --- | --- | --- |
| `BinMap.client.vue` | Client-side Leaflet/OpenStreetMap map. Displays supplied location markers, inspection state, route connections, stop sequence, and depot context. Marker selection can open details. Reused in planner, profile, and manifest. | Specify marker variants, numbered stops, depot icon, route line, loading treatment, and legible legends. Preserve map attribution and straight-line-preview labeling. |

## Project-owned controls used

These are design-system building blocks, not additional screens:

| Vue component | Used for |
| --- | --- |
| `WorkspaceSidebar` | Native button navigation, active module, permanent icon-only presentation. |
| `UiButton` | Primary, outline, plain, disabled, and loading actions. |
| `UiIconButton` | Plan-drawer toggle. |
| `UiIcon` | Recycling, lock, navigation, and action symbols. |
| `UiInput` | Location UUID search. |
| `UiSegmentedControl` | Glass-material filter. |
| `UiSelect` | Material and sort filters. |
| `UiSlider` | Minimum recorded-fill threshold. |
| `UiCheckbox` | Individual bins and partial/full group selection. |
| `CollectionDatePicker` | Calendar picker inside `CollectionDatePicker.vue`. |
| `UiCard` | Bin, location, metric, analytics, export, and status panels. |
| `UiTag` | Material badges, Locked indicator, and health statuses. |
| `UiTable` | Observation and analytics tables. |
| `UiPagination` | Location, history, and monthly-data pagination. |
| `UiTextarea` | Draft collector notes. |
| `UiInfoCard` | Error, empty, and unavailable states. |
| `UiLoadingIndicator` | Loading feedback. |

These controls live in `app/shared/ui/controls`; the calendar lives in `app/shared/ui/CollectionDatePicker.vue`. No external UI component library is required.

## How the components fit together

```text
app.vue
├── WorkspaceSidebar
├── WorkspaceHeader → CollectionDatePicker
└── Active module
    ├── PlanningView
    │   ├── PlanningFilters
    │   ├── LocationClusterList → LocationClusterCard → HistoricalFillMeter
    │   └── PlanningMapPanel → BinMap.client + RoutePlanDrawer
    ├── HistoryView → CollectionDatePicker + HistoryTable
    ├── LocationDetails
    │   ├── LocationProfileCard → BinMap.client
    │   └── BinFractionCard + HistoricalReadingsChart + HistoryView
    ├── CollectionManifest
    │   └── PlanMetrics + ManifestStopCard + BinMap.client + ExportActions
    ├── CollectionAnalyticsView
    │   ├── AnalyticsSummaryCards + FillDistributionPanel
    │   └── MaterialAnalyticsTable + MonthlyCollectionTable
    ├── ForecastIntegration
    └── SystemStatus
```

Shared badges, metric cards, the global Locked indicator, recovery states, and date pickers must remain consistent across their parent components.

## Recent design decisions to preserve

- Green **Garbage Collector** title in the top header.
- No duplicate product name or “LOGISTICS · HEILBRONN” text in the sidebar.
- No “Waste logistics workspace” or “Municipal glass collection” header subtitle.
- No visible “Planning date · inclusive” label or persistent date-range + 7 days helper text. Keep the accessible hidden label and actual date restrictions.
- Chevron icon to expand/collapse the collection-plan drawer, with adequate contrast.
- Do not restore the removed sidebar database-source block or footer implementation labels.

## Requested output

1. A reusable component sheet covering every component above, grouped by feature, with shared visual tokens and variants.
2. A desktop planner showing selected bins, map, open plan drawer, and the permanent icon-only sidebar.
3. Location details, inventory/history, collection manifest, analytics, forecast-pending, and system-status screens composed from those same components.
4. Detailed date-picker designs for the closed field and open calendar, including selected, focused, and disabled days and date navigation.
5. Tablet/mobile planner and collection-plan layouts, plus a printable collector manifest.
6. Applicable loading, empty, error, hover, focus, disabled, indeterminate, selected, and unselected states.

Use realistic illustrative content without presenting fabricated readings, addresses, predictions, or operational savings as actual data. Prioritize readability, efficient selection, and a clear review-to-export workflow.

The full historical-cutoff banner has been removed from all modules. Show only a compact lock icon with “Locked” at the top right; its tooltip explains the active cutoff date and exclusion of later records. Keep it visible on mobile.
