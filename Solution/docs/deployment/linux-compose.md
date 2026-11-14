# Linux deployment with Aspire and Docker Compose

The AppHost now supports both local development and Docker Compose publishing. Production runs the published ASP.NET API and Nuxt's `start` script (`node .output/server/index.mjs`). App dependency installation, build, and startup use pnpm.

```text
HTTPS reverse proxy → 127.0.0.1:3000 → Nuxt container → api:8080
                                                        ↓
                                server data directory → /data (read-only)
```

The API has no published host port. The production Aspire dashboard is disabled. Nuxt is published on localhost so it can sit behind an existing HTTPS reverse proxy. Neither the API nor Nuxt requires a systemd unit; Compose configures both containers with `restart: unless-stopped`.

## 1. Prepare the Linux server once

Install:

- .NET 10 SDK, used by Aspire and API container publishing.
- Docker Engine and Docker Compose, with the daemon running and available to your deployment account.
- Aspire CLI compatible with the pinned 13.6.5 AppHost packages. See [installation instructions](https://aspire.dev/get-started/install-cli/).

The frontend builds inside its generated Node 22 container. Host-side Node/pnpm are still required for local `dotnet run --project apps/apphost`, but are not required for these container build stages.

Copy or clone the repository onto the server. Run deployment commands on that server; they operate on the Docker host available to the command, not automatically on a remote machine.

From the repository root, put the existing database in a persistent directory:

```sh
sudo install -d -m 0755 /var/lib/garbage-collector
sudo cp -n sql.db /var/lib/garbage-collector/sql.db
sudo chmod 0644 /var/lib/garbage-collector/sql.db
```

`cp -n` preserves an already-present database. The directory must allow traversal and the file must be readable by the API's container identity. These example permissions assume the deployment data may be read by local server users; use more restrictive ownership/group permissions where appropriate.

SQLite is opened read-only. The application never seeds, migrates, or creates the source database. Back up the server copy separately. Use a consistent SQLite backup/snapshot if another process is writing the source file during a data transfer.

To use a different host directory, export an absolute path before deploying:

```sh
export GARBAGE_COLLECTOR_DATA_DIR=/srv/garbage-collector-data
```

That directory must contain `sql.db`. The container path remains `/data/sql.db`; the development `Database__Path` setting is separate and is not used as a container path. Generated Compose uses `${GARBAGE_COLLECTOR_DATA_DIR:-/var/lib/garbage-collector}`, resolved by Docker Compose on the deployment host.

For MapTiler OMT, export `NUXT_PUBLIC_MAPTILER_API_KEY` before deploying. Compose forwards it to Nuxt at runtime. The style is the normal `openstreetmap` OMT style. With no key configured, the existing OSM basemap remains available. Create your own [MapTiler key](https://docs.maptiler.com/guides/developer/credentials/api-key/) and configure its allowed domains. MapTiler/OSM attribution and the MapTiler logo remain visible.


## 2. Deploy

From the repository root on Linux:

```sh
aspire deploy --apphost apps/apphost/GarbageCollector.AppHost.csproj --environment Production -o aspire-output
```

Aspire publishes the configuration, builds the images, fills image references, and starts Compose. The source database is mounted from the server, not copied into an image. Keep the same data-directory environment setting on subsequent deployments.

Check the application after startup:

```sh
curl --fail http://127.0.0.1:3000/api/health
docker compose -f aspire-output/docker-compose.yaml --env-file aspire-output/.env.Production ps
docker compose -f aspire-output/docker-compose.yaml --env-file aspire-output/.env.Production logs --tail 100
```

The health endpoint should return `{"status":"healthy"}`. Nuxt's Compose health check calls that endpoint, verifying the frontend proxy, API, and required database tables together. Production startup ordering waits for the API container to start; its readiness is then checked through the frontend health check. Give the services time to initialize before investigating an initial failed check.

Aspire writes an environment-specific file during deployment (for the example environment, `.env.Production`). Use the actual filename reported by the CLI if its naming differs. A plain `.env` from **publish only** contains unresolved image placeholders and is not sufficient to start containers.

The generated Node Dockerfile uses the pinned pnpm version for application commands. Aspire bootstraps that pnpm executable using tooling supplied by the Node base image; there is no application npm install workflow.

## 3. Open the application

For private verification from your own computer, use an SSH tunnel:

```sh
ssh -L 3000:127.0.0.1:3000 your-user@your-server
```

Then open http://localhost:3000 on your computer. Choose a different local tunnel port if your development app already uses 3000.

For a public domain, configure your existing Nginx/Caddy/other reverse proxy to forward to `http://127.0.0.1:3000`, with HTTPS and access protection. The application currently has no login. The API stays on the private Docker network and Nuxt continues proxying browser `/api` requests internally. See [the Nginx location example](nginx-location.conf.example).

## Publish files without deploying

```sh
aspire publish --apphost apps/apphost/GarbageCollector.AppHost.csproj --environment Production -o aspire-output
```

This generates `docker-compose.yaml`, `web.Dockerfile`, and `.env` without building or starting containers. Publishing produces image placeholders; `aspire deploy` or the prepare pipeline builds/resolves them. Do not run `docker compose up --build` against publish-only artifacts expecting it to build the API: the Compose services reference images produced by Aspire's pipeline.

The generated directory is ignored by Git. Keep the AppHost as the source of truth, and change `ComposeDeployment.cs` rather than editing generated YAML.

## Updating and troubleshooting

- Update the source and run the same `aspire deploy` command. The SQLite bind directory persists independently of container replacement.
- Missing database: check the host directory, `sql.db` filename, file permissions, and API logs. Docker may create a missing bind directory, but the API will fail rather than create an empty database file.
- Unhealthy web container: check API startup, database access, and Nuxt logs. Inside the web container the API address is `http://api:8080`, not localhost.
- Port conflict: stop an existing development server using port 3000, or change the published port policy in `ComposeDeployment.cs` and republish.
- Architecture: deploy/build on the target Linux server so images match its architecture. A locally built Apple Silicon image is not automatically an x64 Linux image.
- Backups: retain a copy outside the container and release directories before replacing the historical dataset.
- Map tiles require outbound internet access. Review the chosen tile provider's terms before wider use.

## Verification status

The AppHost and tests build. Regression tests cover production bindings, container database paths, dashboard exclusion, read-only bind policy, API privacy, web exposure, and health checks. The actual publishing pipeline generated the Compose YAML and Nuxt Dockerfile, and `docker compose config` accepted the generated file with validation image references.

Container image builds, container startup, live Linux health checks, and reverse-proxy configuration have not been verified here because the local Docker daemon is not running. No server was contacted or deployed to.

References: [Aspire Compose deployment](https://aspire.dev/deployment/docker-compose/), [JavaScript production publishing](https://aspire.dev/deployment/javascript-apps/), [publish CLI](https://aspire.dev/reference/cli/commands/aspire-publish/), [deploy CLI](https://aspire.dev/reference/cli/commands/aspire-deploy/).
