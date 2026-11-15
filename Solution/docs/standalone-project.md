# Standalone application and hand-off

`Solution/` is the complete project. It can be copied into another directory, renamed or made into its own repository. Original contributor folders and the parent repository are not build, test or runtime dependencies. Preserve `sql.db` at the project root; the application opens it read-only.

## Ownership and paths

| Part | Canonical source |
| --- | --- |
| Seasonal forecast, selection, multi-load routing, road provider and digital twin | `forecast_service/vendor/fillinq/` |
| Bundled engine regression tests | `forecast_service/tests/engine/` |
| JSON/stdin adapter, cost/timing insights, validation and comparison | `forecast_service/worker.py`, `forecast_service/integrations/` |
| Worker and relocation tests | `forecast_service/tests/` |
| API, web and local orchestration | `apps/api/`, `apps/web/`, `apps/apphost/` |
| Read-only source database | `sql.db` |

The twelve engine Python modules were copied byte-for-byte from the working implementation. Development imports the bundled package unconditionally. Change these bundled files for future engine work; the sibling engine is not imported. The .NET content rules publish these same files under `forecast_service/vendor/fillinq`. All engine tests run under the single `forecast_service/tests` target.

The API Dockerfile takes the project root as context, copies `apps/api` and the bundled Python source, and publishes without reading a sibling directory. Aspire derives that context from the AppHost's project-relative path, without requiring the directory to be named `Solution`. Its production data mount remains separate and read-only.

`.gitignore` and `.dockerignore` are local to this project. Environments, credentials, build outputs, caches, backups, generated deployment files and the source database are excluded from the container context. The database must remain in a source hand-off or be supplied separately; it is deliberately absent from published API files and images.

## Start from a clean copy

Copy the directory contents without `.venv/`, `node_modules/`, `bin/`, `obj/`, `.nuxt/`, `.output/`, caches, private `.env` files, `backups/` or `aspire-output/`. Recreate dependencies rather than copying a virtual environment, whose executable scripts can contain absolute paths.

From the copied project root:

```sh
make setup PYTHON=python3.12
make check
make run
```

.NET 10, Node 22.23+, pinned pnpm and Python 3.12 are required as documented in the README. Package installation and road/map services still need network access. A Gurobi license remains optional for bounded independent checks; unavailable licenses are reported explicitly.

For a Docker-capable deployment host:

```sh
docker build -f apps/api/Dockerfile -t garbage-collector-api .
```

For the complete two-service deployment use the [Aspire/Compose guide](deployment/linux-compose.md). Docker Engine and Aspire CLI must be installed/running on that host. Supply the read-only source database separately.

## Verification

A fresh temporary directory named `independent-app` was created outside the repository with no sibling contributor projects. No environments, dependencies, build outputs or generated deployment files were copied. The actual `make setup PYTHON=python3.12` installed fresh Python dependencies, restored .NET projects and installed pinned frontend dependencies there.

`make check` in that renamed copy passed all **418 tests**: **216 API, 6 AppHost, 144 frontend/tooling and 52 Python**, plus type checking, .NET builds and the Nuxt production build. Relocation regressions copy the Python service again and exercise real JSON/stdin forecast and empty-proposal calls from an unrelated working directory, with a conflicting ambient package present.

An actual Release `dotnet publish` in the isolated project included all twelve engine modules with matching hashes and no database file. Its published Python worker successfully forecast from another working directory. AppHost tests verify the project-local Docker context and production bindings. Docker image execution is not verified: the Docker daemon was not running in this environment.

The relocated Aspire app was started using its own copied database and newly installed environment. Live browser verification is recorded separately below. Original SQLite content was preserved throughout.

Live browser checks on the relocated app passed for historical analytics, material/ranking filters, location inspection, forecasting, street-shaped route geometry and reconciled road distances, payload/shift limits, unique stop ownership, truck/load controls and popups, mobile bounds, and accepted-manifest route preservation. Both browser runs reported zero page JavaScript errors. A mobile table-scroll issue exposed during verification was corrected and the route checks repeated successfully. The final frontend builds include that correction.
