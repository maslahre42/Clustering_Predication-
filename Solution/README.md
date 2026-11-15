# Garbage Collector

**Challenge handover:** [demo guide, deliverables and current verification](docs/challenge-demo-guide.md). The connected prototype includes CSV upload, historical pattern charts and review flags, forecasts/groups, configurable multi-load routes and fleet recommendations, simulation, configured glass compartments, editable cost estimates, time-to-full ranges, scenario baselines, a guided presentation and collector export. Latest checks: **491 tests passed**, type checking and both builds passed. The guide records live verification and prototype limits.

**Street routing:** optimized routes use OSRM car-street distances, driving times and map geometry. Trucks keep compact collection sectors across loads. Fixed-time and aerial-distance controls are removed; optional detour value defaults to zero. See [routing method, provider/cache configuration and limits](docs/architecture/street-routing.md).

**Forecasts and simulation:** open **Forecast, routes & simulation** in the sidebar, then **Forecast curves** or **Simulation & backtest** at the top. This now runs Omar's actual Python seasonal model, OR-Tools router and digital twin. Run `make setup-python PYTHON=python3.12` once for an existing checkout, then restart the API/Aspire host. New `make setup` includes Python setup. [Method, parameters, limits and API](docs/architecture/proposal.md).

Local ASP.NET Core 10 + Nuxt 4/Vue foundation for historical glass-bin collections demonstrated in Karlsruhe.

For code changes, start with the [code index](CODE_INDEX.md) and [contributor guidance](AGENTS.md). They map each feature to its source and tests.

## Standalone project

This directory is the complete application. Copy only `Solution/` (including `sql.db`) to a new location; the directory can be renamed. No sibling project folders or parent repository are required. Run commands from the directory containing this Makefile and `GarbageCollector.slnx`.

The forecast/routing engine is bundled in `forecast_service/vendor/fillinq`, with tests in `forecast_service/tests/engine`. Other integrations are already inside `forecast_service/integrations`. Docker uses this directory as its build context:

```sh
docker build -f apps/api/Dockerfile -t garbage-collector-api .
```

Exclude `.venv`, `node_modules`, build outputs, caches, local `.env` files, `backups/` and `aspire-output/` from a source hand-off. Recreate dependencies with `make setup PYTHON=python3.12`. Keep `sql.db` unchanged; production mounts a read-only copy separately. The local ignore files travel with the standalone project. See [standalone verification](docs/standalone-project.md).

## Requirements

- Python 3.12 (verified) for forecasts, routing and simulation.
- .NET SDK 10 (global.json accepts installed .NET 10 feature bands).
- Node >= 22.23 and pnpm 10.12.1 (pinned in the frontend package.json).
- Existing `sql.db` at the repository root with `raw_data` and `locations` tables.
- GNU Make for the shortcuts below (macOS/Linux; Windows users can use WSL).

## Quick commands with Make

Run commands from the repository root. `make` or `make help` lists all shortcuts. They wrap the existing .NET, pnpm, and Aspire commands, so contributors do not need to remember their syntax.

```sh
make setup       # Restore backend packages and install frontend dependencies
make run         # Start the full app with Aspire; Ctrl+C stops it
make test        # API, Aspire and frontend tests
make check       # Tests, type checking and all builds
```

Run `make setup` first on a fresh checkout. The existing `sql.db` must be present; setup does not create or modify it. Open http://localhost:3000 after startup. After backend code changes, stop and rerun `make run` to pick them up.

| Command | Purpose |
| --- | --- |
| `make dev` | Alias for `make run` |
| `make api` / `make web` | Start servers separately, each in its own terminal |
| `make test-api` / `make test-web` | Run only the backend/AppHost or frontend tests |
| `make typecheck` | Check Vue and TypeScript types |
| `make build` | Build the .NET solution and production Nuxt server |
| `make build-api` / `make build-web` | Build only one side |
| `make smoke` | Check an already-running API; `API_BASE` overrides its address |
| `make clean` | Remove .NET/frontend build outputs, frontend dependencies, caches, and `.DS_Store` files; keep databases, source, design references, and deployment files |
| `make compose` | Generate Compose files without deploying; Aspire CLI required |
| `make deploy` | Deploy on the current Docker host; see the [Linux deployment guide](docs/deployment/linux-compose.md) |

Use `make build CONFIGURATION=Release` for a Release backend build. Compose commands accept `ENVIRONMENT=Production` and `OUTPUT_DIR=aspire-output`; these are the defaults. Tool executables can be overridden with `DOTNET`, `PNPM`, `PYTHON`, and `ASPIRE`. Stop the app before `make clean`, then run `make setup` before building or starting it again. Cleaning removes backend outputs for all configurations.

## Run locally

### Start everything with Aspire

From the repository root:

```sh
dotnet run --project apps/apphost
```

This starts the Aspire dashboard, ASP.NET API, and Nuxt development server. Aspire runs `pnpm install --frozen-lockfile`, waits for the API's `/api/health` database check, and injects the API address into Nuxt through `NUXT_API_BASE`. Open http://localhost:3000 for the application and use the authenticated dashboard link printed in the terminal (port 15888) for resource status and console logs. Stop the AppHost with Ctrl+C to stop its child processes.

Node and pnpm must be on PATH. No Docker, Azure account, or separately installed Aspire CLI is required for these process-based resources. The AppHost uses pinned Aspire 13.6.5 packages. Its local launch profile uses HTTP on localhost and retains dashboard token authentication. Do not run the standalone servers on the same ports at the same time.

The SQLite file remains read-only and is used only by the API. `Database__Path` overrides are forwarded by the AppHost, with relative paths resolved against `apps/api`, matching standalone startup. See [the Aspire architecture notes](docs/architecture/aspire.md) for configuration and diagnostic scope.

### Start each application separately

From the repository root, in terminal 1:

```sh
dotnet restore apps/api/GarbageCollector.Api.csproj
dotnet run --project apps/api
```

In terminal 2:

```sh
cd apps/web
pnpm install
pnpm dev
```

Open http://localhost:3000. The API listens at http://localhost:5080. Nuxt proxies browser `/api` requests to ASP.NET so browser CORS configuration is unnecessary.

## Deploy to a Linux server with Aspire

The AppHost now publishes Docker Compose services for the API and production Nuxt server. Prepare the server's persistent SQLite directory, then run on that server:

```sh
aspire deploy --apphost apps/apphost/GarbageCollector.AppHost.csproj --environment Production -o aspire-output
```

Requires the .NET 10 SDK, Aspire CLI, and a running Docker Engine with Compose. Nuxt is available at `127.0.0.1:3000` for an HTTPS reverse proxy or SSH tunnel; the API stays private. The server's `/var/lib/garbage-collector/sql.db` is mounted read-only. `GARBAGE_COLLECTOR_DATA_DIR` overrides that host directory. The production dashboard is disabled.

See [Linux deployment instructions](docs/deployment/linux-compose.md) for first-time setup, publish-only commands, image/environment handling, health checks, and the verification limits. The generated Compose file validates; image builds and live containers remain unverified because Docker is not running in this environment.

## Runtime configuration

- API: `Database__Path` overrides the SQLite path (relative to the API content root or absolute). The default points to the root `sql.db`.
- Web: `NUXT_API_BASE` overrides the backend origin, including in the built Node server. Default: `http://localhost:5080`.
- Maps: `NUXT_PUBLIC_MAPTILER_API_KEY` enables MapTiler OMT tiles. Set it in `apps/web/.env` for local Nuxt development, or export it before Compose deployment. The map uses the normal `openstreetmap` OMT style. Without a key the standard OSM map remains usable. See [MapTiler API keys](https://docs.maptiler.com/guides/developer/credentials/api-key/); these browser-visible keys should be restricted to your domains. No CSS color filtering is used.
- Backend host binding: `ASPNETCORE_URLS`; adjust `AllowedHosts` for your deployment.

The database is opened **read-only**. No migrations, seeding, `EnsureCreated`, or schema changes run on startup. Missing files fail startup rather than silently creating an empty database. Historical rows are mapped as keyless EF entities because the source table has no primary key. Fill percentages are converted to nullable numbers in API responses. The explicit `overfull` category is preserved as `isOverfull` in history and `lastIsOverfull` in planning summaries, with a null numeric percentage. Malformed or out-of-range values remain unknown; no 110% value is invented.

## Selected-day fill

The planner defaults to **Selected-day estimate** with **Estimated fill ≥ 50%**. Reset filters restores 50%. Recorded visits reset the modeled bin to zero on that date; following days estimate new accumulation from the last recorded emptying. For example, 100% before emptying on 30 September does not remain the current fill on 1 October. **Last recorded before emptying** restores the historical reading. Filters, sorting and location details follow the selected view. Missing/failed estimates stay unknown, and source history is preserved. Only recorded visits reset bins; a new date or proposed route does not execute a collection. [Semantics and verification](docs/architecture/selected-day-fill.md).

## API

- `GET /api/health`: verifies access to both required tables.
- `GET /api/data-range`: global observation date bounds and the maximum planning date (last observation + 7 days).
- `GET /api/locations`: locations and synthetic-coordinate flags.
- `GET /api/planning?asOf=2026-03-01`: historical snapshot through the required ISO date (inclusive). Returns only known bins, counts, date bounds, and latest pre-emptying readings at that cutoff. Records after the cutoff are filtered in SQLite and excluded again by the summary rules.
- `GET /api/fill-state?asOf=2026-10-01`: modeled fill after recorded emptyings on the selected day; later dates estimate refill. Historical readings remain unchanged.
- `GET /api/analytics?asOf=2026-03-01`: cutoff-safe material/monthly collection statistics, fill distributions, median intervals, and sparse-history counts.
- `GET /api/history`: paginated observations; optional `locationId`, `material` (`brown`, `green`, `white`), `from`/`to` and `asOf` (`yyyy-MM-dd`), `page` (default 1), `pageSize` (default 50, maximum 200), partial `locationSearch`, `sortBy` (`date`, `location`, `material`, `fill`) and `sortDirection` (`asc`, `desc`; default newest first). Sorting applies before pagination; unknown fill stays last and overfull remains a distinct category. Date bounds are inclusive. `asOf` is an upper bound even when `to` is later.
- `GET /openapi/v1.json`: OpenAPI contract on the backend.

Each bin is identified by `(locationId, material)`. Fill readings are taken before emptying and must never be presented as current bin status. Location coordinates are fake demo points, shared by all three bins at each location.

## Checks and production build

```sh
dotnet build apps/api/GarbageCollector.Api.csproj
cd apps/web
pnpm typecheck
pnpm build
pnpm start
```

Use pnpm for all frontend dependency changes and commit `apps/web/pnpm-lock.yaml`. For reproducible installs, run `pnpm install --frozen-lockfile`. NuGet versions are pinned in the API project; update to maintained .NET 10 patches before deployment.

## Scope and deployment notes

This is a reusable application template with actual historical data, not a simulated dashboard.

- Pick a planning date and click **Apply date**. The picker spans the earliest database observation through seven days after the latest, inclusive. An initial date outside this range defaults to the latest observation; empty data disables selection. Only observations dated on or before that day are used. This is an inclusive, end-of-day replay: same-day records are included because the source has dates, not measurement times.
- Changing the cutoff recreates the planning/history views and clears selected bins and routes. Records are never deleted from SQLite.
- Counts, date bounds, known bins, latest readings, and selectable collection stops come only from eligible observations. Bins first observed after the cutoff do not appear.
- History filters also respect the same cutoff, including when requesting a later `to` date.
- Fill values in planning, history and analytics are actual pre-emptying measurements, never estimates of current fill. Forecasts exist only in the **Forecast, routes & simulation** module (`GET /api/proposal`, `/api/forecast`, `/api/simulation`), where every number is labelled as a prediction; see [method and evidence](docs/architecture/proposal.md).
- Select individual bins or add the actual recorded collections from the selected day. Bins at the same location share one stop.
- Location names use existing UUIDs rather than invented station names. Coordinates and central depot remain synthetic, explicitly labeled. Route preview uses nearest-neighbor order and straight lines, not driving directions or a globally optimal route.
- Export a dated CSV plan with source collection dates and historical percentages. Plans are held in memory.
- Project-owned Vue controls supply the fixed icon rail, calendar, forms, cards, tables, pagination, and action buttons. The interface follows the uploaded `idea of UI:UX` designs, with shared CSS tokens and no Onyx runtime dependency. Leaflet handles the map.

Run frontend unit tests from the repository root:

```sh
pnpm --dir apps/web test
```

Omar’s Python forecasting, constrained OR-Tools routing and digital-twin simulation are connected in **Forecast, routes & simulation**. Truck-specific access profiles, color-chamber constraints and verified operating assets remain extensions.

Leaflet uses MapTiler OMT when a browser key is configured, otherwise the public OpenStreetMap tile service for local demonstration. Provider attribution stays visible. Choose a suitable tile provider and review its usage policy before wider deployment; no offline tile downloading is implemented. The map needs an internet connection.

This is a local development foundation with no authentication. Before exposing it, add access controls, HTTPS, deployment host configuration, and database backup procedures. Keep the database on a persistent local volume when deploying the API. Deploy the built Nuxt Node server alongside the API, configuring `NUXT_API_BASE` to the internal API address. The Python integration reads observation snapshots without changing the database. Future writes should use an explicitly designed schema/migration process, preserving original observations.

See [PROJECT_IDEA.md](PROJECT_IDEA.md) for the product plan and remaining decisions.

## Verification status

Current verification: **491 tests passed** (216 API, 6 AppHost, 175 frontend/tooling, 94 Python), plus Vue/TypeScript checking, .NET solution build and Nuxt production build. The explicitly requested Karlsruhe coordinate replacement preserves all collection records and the original schema; see [provenance and backup](docs/karlsruhe-locations.md).

Live API and browser checks cover the real-data challenge workflow, partial-month statistics, forecast and route feasibility, simulation, uploads, manifest export and draft clearing. See [the challenge handover](docs/challenge-demo-guide.md) for settings, measured results, artifacts and limitations. Physical printing, production hosting and real road operations are separate checks.

Against a running API:

```sh
python3 scripts/smoke-test.py
python3 scripts/challenge-smoke.py --report /tmp/challenge-evidence.json
```

The second command expects the bundled source dataset and takes longer because it executes forecasts, route search and simulation. To build alongside the dev server without sharing Nuxt's build directory, use `NUXT_BUILD_DIR=.nuxt/challenge-build make build-web`.

## Unit tests

Run both suites from the repository root:

```sh
dotnet test GarbageCollector.slnx
pnpm --dir apps/web test
```

Backend tests use xUnit with in-memory observation fixtures and isolated SQLite databases. They do not start the API, open `sql.db`, or change its records. Coverage includes supported materials, strict ISO dates and leap days, inclusive ranges, pagination bounds and overflow, culture-independent percentage parsing, malformed/unknown values, bin identity by location plus material, collection counts, choosing the latest pre-emptying reading, inclusive historical cutoffs, future-only bins, dates before the first observation, and ensuring later additions do not change a past snapshot. The production endpoints call the same rules and summary functions covered by these tests.

Frontend tests use Node's built-in test runner against the TypeScript planning utilities; no additional test dependencies are needed. Coverage includes geographic distance (including the antimeridian), nearest-neighbor ordering, colocated stops, grouping multiple glass bins into one location stop, empty plans, and the return leg to the depot. The application uses these same helpers. Workspace tests also cover historical joins, unknown-fill filtering, grouping glass fractions, and CSV escaping.

Optional backend coverage report:

```sh
dotnet test GarbageCollector.slnx --collect:"XPlat Code Coverage"
```

Verified results: **216 API tests, 6 AppHost tests, 175 frontend/tooling tests and 94 Python tests pass (491 total)**. Backend tests cover shared domain/validation/snapshot/analytics rules, dataset date bounds, and isolated SQLite readers. The frontend tests include date validation and the actual reactive workspace state model (selection, filtered grouping, navigation, stop ordering, errors, and immediate clearing on cutoff changes).

For environments where the standard `dotnet test` runner cannot start its communication socket, a fallback is included. A small in-process runner calls the real xUnit discovery/execution API, including theories and async fixtures; it does not replace assertions or manually call test methods. Run both suites without a local test socket:

```sh
./scripts/test.sh
```

Or run just the backend fallback:

```sh
dotnet build tests/GarbageCollector.TestRunner --no-restore -p:UseSharedCompilation=false -m:1
dotnet tests/GarbageCollector.TestRunner/bin/Debug/net10.0/GarbageCollector.TestRunner.dll
```

The fallback exits nonzero on failed tests, discovery errors, timeout, or zero discovered tests. No server is started. NuGet may report `NU1900` if the vulnerability feed is unavailable; package auditing remains enabled.

Unit/service tests complement `scripts/smoke-test.py`; HTTP transport, browser rendering, map interaction, PDF print layout, and live external services are outside their scope.

## Designer-inspired component architecture

The uploaded designs in `idea of UI:UX` informed the persistent navigation rail, neutral/green palette, historical cutoff strip, split list/map canvas, glass-fraction cards, route drawer, detail page, and manifest. Their sample streets, vehicles, live sensors, model outputs, and performance figures are not used as application data.

The frontend is split into small components under `apps/web/app/features/*/components`, `components/layout`, and `shared/ui`. `useCollectionWorkspace` provides one shared reactive workspace: selected bins survive navigation, manual stop ordering and draft collector notes are shared with the manifest, and changing the cutoff clears the plan. Export CSV uses one row per selected bin and preserves its original collection date. Browser print provides a PDF-capable collector sheet. Draft notes and plans are not written to SQLite.

The fill slider filters the **last recorded pre-emptying reading**, not present fill or predicted urgency. The bin detail chart plots individual real observations; no accumulation curve or forecast is invented. Model forecasts and estimated loads are available in the forecast module. Live dispatch, measured vehicle weights and verified vehicle metadata require operating data. Fonts use Hanken Grotesk/Inter when installed, with system fallbacks; no font assets were included in the design upload.

See [component and design mapping](docs/architecture/ui-components.md) for responsibilities and source mapping. Restart `pnpm dev` after the component-directory configuration change. The backend API contract and read-only database remain unchanged.

## Historical analytics and overfull readings

The `Historical analytics` module implements useful exploratory metrics from `main.ipynb` while preserving the confirmed data semantics:

- Every eligible record is a pre-emptying collection observation. Emptyings are not inferred from drops between readings.
- `overfull` is a distinct observed category, never silently unknown or replaced with 110%.
- Bin cards, history, manifests, and CSV exports preserve overflow flags. The historical fill threshold includes overfull readings even at 100%; highest-fill sorting places them above numeric 100%. This describes a past collection, not current urgency.
- Numeric means exclude overfull and unknown readings; the numeric denominator is shown. Overfull rates use all eligible collection records as their denominator.
- Intervals use consecutive distinct collection dates within each `(locationId, material)` and are pooled by material for the displayed median. Single-observation bins contribute no interval. Values are not accumulation rates.
- Fill distributions use descriptive bands: 0–30, above 30/below 70, 70/below 100, exactly 100, overfull, and unknown. They do not label collection decisions as necessary or wasteful.
- Sparse history means fewer than three observations by the cutoff; this is a coverage indicator, not a forecast confidence score.
- Monthly tables use only records through the selected date, so the last month can be partial. No seasonal causality is claimed.

All analytics respect the inclusive planning cutoff. SQLite and the notebook are unchanged. Restart the ASP.NET backend after this API update.

## Code architecture

The backend uses feature folders with shared cutoff/fill domain types and isolated EF persistence. Vue features colocate components, models, query adapters, and styles. API contracts, routes, configuration, and browser effects have explicit owners; components consume narrow workspace capabilities.

See [code structure and change guide](docs/architecture/code-structure.md) for the current tree and where to make common changes. Depot defaults are injectable, and real/synthetic coordinate flags now survive joins, map data, and CSV. Constrained operational routing is connected through Omar’s Python engine. Verified coordinate import and road-network navigation remain future work. Restart the frontend dev server after this component-directory reorganization.

The [combined Python integration](docs/combined-project-integration.md) adds Kaise’s CSV validation and guarded behavioral groups, Zakaria’s median-policy simulation and independent Gurobi checks, and a matched real-observation comparison of all three forecast methods. CSV imports are scoped to the analysis workspace; the original SQLite inventory remains unchanged.

The current demo uses 449 mapped glass-container sites in Karlsruhe and nearby Landkreis municipalities. Collection histories retain their original UUIDs and remain synthetically assigned to these sites. See [coordinate provenance and rollback](docs/karlsruhe-locations.md).

The provider-focused [capacity and frequency comparison](docs/architecture/capacity-planning.md) changes physical containers per site/type and calendar-day collection intervals, then compares average filling time, daily shifts, overflow and financial costs under constant demand. The confirmed €500 truck-day package includes truck, driver and driving kilometres. No additional €/km is charged by default; container rental/ownership remains unpriced until entered.

Automatic [joint inventory and scheduling](docs/architecture/joint-planning.md) chooses physical containers and per-type collection calendars, checks routed costs and shift/capacity feasibility, enforces a configurable 90% fill target, and returns a verified repeating daily route calendar. It reports the best feasible solution found, with explicit space/cost/data assumptions; completed results survive module navigation in the same session.
