# Local orchestration with Aspire

`apps/apphost/GarbageCollector.AppHost.csproj` is the local development composition root. `Program.cs` creates the host; `WorkspaceResources.cs` declares the application processes and their dependencies. It does not contain application or collection-planning rules.

## Resource graph

```text
API → existing read-only sql.db
  ↑ wait until /api/health succeeds
Nuxt ← pnpm install --frozen-lockfile
```

The API uses its existing HTTP launch profile. Aspire manages its endpoint and supplies the resolved address to the Nuxt server as `NUXT_API_BASE`; browser requests continue through Nuxt's existing `/api` proxy. The frontend endpoint is http://localhost:3000. Nuxt receives its actual listening port through `PORT`.

`Database__Path` may be absolute or relative to `apps/api`. The AppHost resolves and forwards it explicitly, avoiding dependence on the process working directory. The API retains its existing read-only connection and missing-file validation. There is no database resource, container, migration, seed operation, or source-data mutation.

## Startup

Run from the repository root:

```sh
dotnet run --project apps/apphost
```

Requires .NET 10, Node, pnpm, and the existing source database. The first run restores Aspire packages and installs frontend dependencies using the committed lockfile. Aspire only starts Nuxt after installation completes and the API is healthy. If database startup fails, inspect API console logs in the dashboard.

The dashboard uses port 15888, OTLP uses 15889, and the resource service uses 15890. These localhost HTTP endpoints are defined in `Properties/launchSettings.json`. Dashboard authentication remains enabled: use the token-bearing link printed at startup. Developer-certificate trust is disabled for this HTTP-only local setup.

The AppHost intentionally uses NuGet-restored orchestration binaries (`AspireUseCliBundle=false`) so `dotnet run` needs no global Aspire CLI. Aspire currently emits advisory ASPIRE010 for this choice. Revisit this setting when upgrading to a release that requires the CLI bundle.

## Diagnostics and scope

The dashboard provides process status, health, endpoints, and console logs. Application OpenTelemetry instrumentation has not been added in this change, so API request traces, structured OTLP logs, and application metrics are not yet populated. The OTLP endpoint is available for a later telemetry integration.

Standalone API and frontend startup commands remain supported. The AppHost is an optional local workflow; Docker Compose production publishing is configured in the same AppHost; HTTPS/domain setup remains external. Do not run both workflows concurrently on the same ports.

## Tests

`tests/GarbageCollector.AppHost.Tests` builds the actual resource graph without starting processes, binding sockets, or opening the database. It verifies database-path resolution, API health dependencies, pnpm configuration, and runtime API-address injection using a fake allocated endpoint. The shared in-process xUnit runner and `scripts/test.sh` include these tests.

## Docker Compose production target

`WorkspaceResources.cs` registers the Compose environment and explicitly publishes Nuxt through its production `start` script. Publish mode supplies `/data/sql.db`, Production environment, container HTTP bindings, and the internal API endpoint. Local mode keeps the original development paths and loopback binding. `ComposeDeployment.cs` controls restart, bind mounts, host port exposure, and end-to-end web health policy. The deployment dashboard is disabled.

The actual pipeline generated valid Compose YAML and a pnpm Nuxt Dockerfile; Docker Compose configuration validation passed. Container image builds and live startup are pending a running Docker daemon. See [Linux deployment instructions](../deployment/linux-compose.md).
