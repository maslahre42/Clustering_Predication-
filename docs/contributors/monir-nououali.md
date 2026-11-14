# Monir Nououali — historical collection planning application

## Contribution and attribution

Monir contributed the application under [Solution](../../Solution/README.md): an ASP.NET Core API over an existing SQLite database, a Nuxt/Vue operations workspace, map and collection-plan tools, historical analytics, automated checks, and Aspire/Compose startup and publishing configuration.

Git evidence: `31c8cba` initially introduces a Solution Git link; `c8128d7` replaces it with the actual application tree. Commits `94ecfa6` and `2406f15` clean up `.DS_Store` tracking and ignore rules; `79e5eed` merges main. The substantive import is evidence of Monir's application contribution, without proving individual authorship of every imported line. The staged readiness review, coordinate documents, backups and database edits are local work in this area and are not independently attributed by a committed author record.

## Business purpose and complete user workflow

The application lets a planner inspect historical glass collections as of a selected date, compare materials and locations, select bins, assemble a collector manifest, reorder stops, add notes, and export/print the result. It deliberately presents historical evidence: a percentage measured immediately before a past emptying does not become today's fill estimate.

The workflow is: load dataset date bounds → apply a planning date → retrieve eligible history and locations → filter/group bins → select individual materials or locations → calculate a route preview → inspect and reorder stops → export a dated collector sheet. Forecasting is an explicit future integration, so this application does not itself recommend collections from predicted overflow.

## 1. Source data and domain rules

Sources: [persistence](../../Solution/apps/api/Infrastructure/Persistence/HistoryDbContext.cs), [connection policy](../../Solution/apps/api/Infrastructure/Persistence/PersistenceRegistration.cs), [fill parsing](../../Solution/apps/api/Domain/Collections/RecordedFill.cs), [cutoff](../../Solution/apps/api/Domain/Collections/HistoricalCutoff.cs).

- `raw_data` maps to observations with location UUID, material, ISO date and raw fill text. It is a keyless EF entity because the source table has no declared primary key.
- `locations` maps one UUID to latitude, longitude and `is_synthetic` provenance. The bin identity is `(locationId, material)`, allowing different glass colors at one physical stop.
- The API opens an existing database in read-only mode. Missing files fail startup; there are no runtime migrations, seeding or empty-database creation.
- Numeric values are parsed with invariant culture and accepted only within 0–100. A case-insensitive, trimmed `overfull` token sets a separate flag and leaves the numerical percentage null. Other invalid values are unknown. Thus zero, unknown and overfull remain distinct.
- Dates are strictly validated as `yyyy-MM-dd`. Historical cutoff inclusion is `observationDate <= asOf`, using ISO-date ordering. It is an inclusive end-of-day view, not a reconstruction of what a dispatcher knew that morning.

## 2. Planning snapshot and date navigation

Sources: [snapshot](../../Solution/apps/api/Features/Planning/PlanningSnapshot.cs), [planning endpoint](../../Solution/apps/api/Features/Planning/PlanningEndpoints.cs), [date metadata](../../Solution/apps/api/Features/Dataset/DatasetDateRange.cs), [frontend date model](../../Solution/apps/web/app/features/workspace/planningDate.ts).

`GET /api/planning?asOf=...` filters observations in SQLite before loading them. The snapshot builder repeats the cutoff check defensively, groups by location/material, and emits the most recent eligible collection date, its fill/overfull state, and eligible collection count. It also returns eligible observation count and earliest/latest dates. Bins with only future observations do not appear.

`GET /api/data-range` returns global earliest/latest observation dates and a maximum planning date seven days after the last observation, capped at the maximum supported date. These global bounds support navigation; they do not inject future rows into the snapshot. The frontend accepts dates only within those bounds, defaults an out-of-range initial date to the latest observation, and disables usable bounds for invalid/empty metadata.

The workspace accepts a snapshot only when its `asOf` exactly matches the active date and there is no data error. A date change synchronously clears selected bins, explicit route order, notes and inspected location. This prevents an old selection from being exported under a new date while requests are still loading.

## 3. Inventory, filtering and location details

Sources: [inventory join](../../Solution/apps/web/app/features/inventory/domain/catalog.ts), [planning filters](../../Solution/apps/web/app/features/planning/state/createPlanningFilters.ts), [fill rules](../../Solution/apps/web/app/shared/domain/fill.ts), [workspace](../../Solution/apps/web/app/features/workspace/model.ts).

The frontend joins eligible bin summaries to location records, preserves coordinate provenance, and builds stable keys `locationId:material`. A bin without a matching location is omitted from the mapped inventory. Location names derive from UUID prefixes rather than invented station names. Grouping combines selected fractions at the same UUID into one stop; this is physical grouping, not behavioral machine-learning clustering.

Filters support location substring search, one material, minimum last historical fill and recent/highest-fill sorting. Overfull passes all fill thresholds, including 100%; unknown readings remain visible at threshold zero and drop out at positive thresholds. For sorting, overfull receives an ordering sentinel above numeric 100, and unknown ranks below numeric values; the sentinel is never exported as a measured percentage. Highest-fill location sorting uses the highest bin rank at that location; recent sorting uses its latest collection date, with UUID tie-breaking.

Details show actual past observations and material fractions. The historical chart is a plot of recorded values, not a simulated accumulation curve or confidence interval.

## 4. History query rules

Sources: [HTTP binding](../../Solution/apps/api/Features/History/HistoryEndpoints.cs), [validation](../../Solution/apps/api/Features/History/HistoryRules.cs), [SQL filters](../../Solution/apps/api/Features/History/HistoryQuery.cs), [reader](../../Solution/apps/api/Features/History/HistoryReader.cs), [fill ordering](../../Solution/apps/api/Features/History/HistoryFillOrdering.cs), [frontend query state](../../Solution/apps/web/app/features/history/state/createHistoryFilters.ts).

`GET /api/history` supports exact location, partial location search, brown/green/white material, inclusive from/to bounds, the shared historical cutoff, pagination and date/location/material/fill sorting. Both `to` and `asOf` apply, so a later `to` cannot bypass the cutoff.

Page defaults to 1; page size defaults to 50 and must be 1–200. Invalid materials, date ranges, sort fields or directions produce a 400 response. Offset calculation uses a wider intermediate integer and clamps to avoid integer overflow. Sorting precedes pagination and uses stable secondary date/location/material ordering.

Fill sorting parses all filtered rows in memory before paging because numeric strings, overfull and malformed values need domain ordering. Unknown always sorts last; descending known fills put overfull ahead of numeric 100. Other fields are sorted/paged in SQL. This is correct for the data size but fill sorting has a larger memory cost as history grows.

The frontend resets page to one when filters or sorting change. Changing date or initial inspected location resets history filters and sort state, and the cutoff remains in every query.

## 5. Historical analytics

Source: [CollectionAnalytics](../../Solution/apps/api/Features/Analytics/CollectionAnalytics.cs).

`GET /api/analytics?asOf=...` applies the same inclusive cutoff and computes:

- Total collection observations, known location/material pairs, explicit overfull counts, and bins with fewer than three observations.
- Per material: collections, numeric count, overfull count, unknown count, mean numeric fill, interval count and median interval.
- Fill bands: 0–30 inclusive; above 30 and below 70; 70 through below 100; exactly 100; overfull; unknown.
- Per month/material: collection count, numeric denominator, numeric mean and overfull count. A final month can be partial at the selected cutoff.

Numeric means exclude overfull and unknown. Overfull rates in the UI use all eligible collection observations, not just numeric rows. Intervals are gaps between consecutive distinct collection dates within a single bin, pooled by material before taking the median; they are collection cadence, not growth rates. A single-observation bin contributes no interval. Sparse-history count is a coverage measure, not forecast confidence. The bands do not prove a collection was avoidable or a service decision was wrong.

## 6. Selection, routing and manifest

Sources: [collection-plan state](../../Solution/apps/web/app/features/manifest/state/createCollectionPlan.ts), [geometry](../../Solution/apps/web/app/shared/domain/geometry.ts), [CSV](../../Solution/apps/web/app/features/manifest/domain/planExport.ts), [manifest UI](../../Solution/apps/web/app/features/manifest/components/CollectionManifest.vue).

Selection accepts only bins in a ready current snapshot. Individual bin selection is deduplicated. Selecting a location adds/removes its currently filtered bins; it need not select hidden fractions. “Add day collections” selects currently filtered bins whose latest eligible collection equals the chosen day. Removing a stop removes all its selected material keys.

Selected materials are grouped by location. Without a manual order, a greedy nearest-neighbor walk repeatedly chooses the nearest unvisited stop from the depot/current point. Haversine distance uses Earth radius 6,371 km. The preview and metric include depot → stops → depot; an empty plan has zero distance. Manual move-up/down swaps preserve an explicit order; newly selected locations are appended after that order.

Notes belong to locations. Export produces one row per selected material, so a multi-material physical stop can produce several rows with the same stop number. Fields preserve planning date, source collection date, nullable pre-emptying percentage, explicit overflow flag, coordinates, synthetic provenance and note. Every CSV cell is quoted, internal quotes are doubled, and CRLF separates rows. Print uses the collector-manifest view. Draft state remains in memory.

The route is a straight-line preview. It does not enforce road access, travel time, vehicle volume/payload, compartments, unloading, shifts or minimum fleet size. No claim of global optimality follows from nearest-neighbor ordering.

## 7. UI architecture and operational delivery

Sources: [workspace adapter](../../Solution/apps/web/app/composables/useCollectionWorkspace.ts), [API proxy](../../Solution/apps/web/server/api/[...path].ts), [Aspire resources](../../Solution/apps/apphost/WorkspaceResources.cs), [Compose policy](../../Solution/apps/apphost/ComposeDeployment.cs), [code index](../../Solution/CODE_INDEX.md).

The interface offers planning, history, analytics, details, manifest, forecast-integration and system-status views. Vue feature state/domain modules own decisions; components render state and emit actions. Narrow injected capabilities give views access to data, navigation, filters or plan operations. Mutable workspace state is request-local rather than a shared singleton. Shared controls implement dates, sorting, pagination, forms and status handling.

Nuxt proxies browser `/api` requests to ASP.NET. Map tiles use MapTiler when configured and OSM otherwise, keeping attribution and synthetic/straight-line disclosures. Retry refreshes bounds and dependent requests. Forecast integration is visibly unconnected; weights, dispatch and vehicle metadata are unavailable.

Aspire starts API and frontend, installs frontend packages using the frozen pnpm lockfile, injects the API origin and waits for database health. Compose publishing keeps the API private, mounts `/data` read-only, exposes the web service on loopback port 3000, sets restart policies and a web health check, and disables the production dashboard. These are authored startup/publishing capabilities, not evidence that production containers were deployed during this review.

## 8. Supporting local geography and review work

The [coordinate document](../../Solution/docs/heilbronn-location-sql-proposal.md) records an already-applied local replacement of 449 location coordinates, with database backup and JSON audit. Its method retains 109 official Heilbronn map points, adds 340 regional mapped glass points outward by distance, rejects regional candidates within 75 m of selected points, and assigns points to UUIDs deterministically by UUID order. All assignments remain synthetic because the original UUID-to-real-site correspondence is unknown. Source URLs and municipality labels are provenance, not proof of historical identity or ten-minute road legs.

The [readiness review](../../Solution/docs/challenge-readiness-review.md) records cross-project findings about observation semantics, evaluation leakage, demand clipping, failure reporting and missing integration. These staged artifacts belong to the current Solution work area; Git does not independently establish their author. The research PDF also remains unattributed in the [index](README.md).

## 9. Existing verification and remaining limits

Tests cover backend parsing/validation/cutoffs/snapshots/analytics/relational history, frontend reactive selection/reset/export/date/filter/sort behavior, actual control interactions, geometry, and Aspire/Compose configuration. See [tests](../../Solution/tests) and the [documented commands/results](../../Solution/README.md). Previously recorded pass counts are historical evidence and were not rerun here.

The strongest implemented business guarantee is that an inclusive historical view preserves recorded fill meaning and coordinate provenance while supporting a reviewable draft collection plan. Remaining gaps include forecast-service integration, constrained road routing, upload processing in this application, persistent dispatch, authentication and operational asset data. The repository contains no evidence that all four contributors' engines are connected to this UI.
