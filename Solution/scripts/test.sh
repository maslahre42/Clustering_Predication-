#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

# Runs API, AppHost resource-graph, and frontend tests.
# Keep package auditing enabled; cached packages can be used if a source is offline.
dotnet restore tests/GarbageCollector.TestRunner/GarbageCollector.TestRunner.csproj --ignore-failed-sources --disable-parallel -m:1
dotnet build tests/GarbageCollector.TestRunner/GarbageCollector.TestRunner.csproj --no-restore -p:UseSharedCompilation=false -nodeReuse:false -m:1
dotnet tests/GarbageCollector.TestRunner/bin/Debug/net10.0/GarbageCollector.TestRunner.dll
pnpm --dir apps/web test
.venv/bin/python -m pytest -q forecast_service/tests ../Omar-Work/tests
