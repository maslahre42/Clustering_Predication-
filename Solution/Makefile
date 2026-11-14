.DEFAULT_GOAL := help

# Builds and tests share generated files, so keep targets serial even with make -j.
.NOTPARALLEL:
.PHONY: help setup run dev api web test test-api test-web typecheck build build-api build-web check smoke clean compose deploy

DOTNET ?= dotnet
PNPM ?= pnpm
PYTHON ?= python3
ASPIRE ?= aspire
CONFIGURATION ?= Debug
ENVIRONMENT ?= Production
OUTPUT_DIR ?= aspire-output

SOLUTION := GarbageCollector.slnx
TEST_RUNNER := tests/GarbageCollector.TestRunner/GarbageCollector.TestRunner.csproj
TEST_DLL := tests/GarbageCollector.TestRunner/bin/$(CONFIGURATION)/net10.0/GarbageCollector.TestRunner.dll

help: ## Show available commands (default)
	@awk 'BEGIN { print "Garbage Collector — run from the repository root\n" } /^[a-zA-Z][a-zA-Z0-9_-]*:.*## / { split($$0, parts, ":.*## "); printf "  make %-14s %s\n", parts[1], parts[2] }' Makefile

setup: ## Restore .NET packages and install pinned frontend dependencies
	"$(DOTNET)" restore "$(SOLUTION)" --disable-parallel
	"$(PNPM)" --dir apps/web install --frozen-lockfile

run: ## Start API, frontend and dashboard with Aspire; Ctrl+C stops them
	"$(DOTNET)" run --project apps/apphost

dev: run ## Alias for run

api: ## Start only the API (use a separate terminal for make web)
	"$(DOTNET)" run --project apps/api

web: ## Start only the Nuxt development server
	"$(PNPM)" --dir apps/web dev

test: test-api test-web ## Run API, Aspire and frontend tests

test-api: ## Build and run API + Aspire tests without VSTest sockets (setup first)
	"$(DOTNET)" build "$(TEST_RUNNER)" --configuration "$(CONFIGURATION)" --no-restore -p:UseSharedCompilation=false -nodeReuse:false -m:1
	"$(DOTNET)" "$(TEST_DLL)"

test-web: ## Run frontend domain, state and component tests
	"$(PNPM)" --dir apps/web test

typecheck: ## Check Vue and TypeScript types
	"$(PNPM)" --dir apps/web typecheck

build: build-api build-web ## Build the .NET solution and production frontend (setup first)

build-api: ## Build API, Aspire and .NET tests (setup first)
	"$(DOTNET)" build "$(SOLUTION)" --configuration "$(CONFIGURATION)" --no-restore -p:UseSharedCompilation=false -nodeReuse:false -m:1

build-web: ## Build the production Nuxt server
	"$(PNPM)" --dir apps/web build

check: test typecheck build ## Run all tests, type checks and builds

smoke: ## Check a running API; override its address with API_BASE
	"$(PYTHON)" scripts/smoke-test.py

clean: ## Remove build outputs, dependencies and caches; run make setup afterward
	rm -rf -- apps/*/bin apps/*/obj tests/*/bin tests/*/obj
	rm -rf -- apps/web/.nuxt apps/web/.output apps/web/node_modules .mypy_cache .pnpm-store
	find . -type d -name .git -prune -o -type f -name .DS_Store -exec rm -f -- {} +

compose: ## Generate Compose files only; requires Aspire CLI
	"$(ASPIRE)" publish --apphost apps/apphost/GarbageCollector.AppHost.csproj --environment "$(ENVIRONMENT)" -o "$(OUTPUT_DIR)"

deploy: ## Build and deploy on the current Docker host; requires Aspire CLI + Docker
	"$(ASPIRE)" deploy --apphost apps/apphost/GarbageCollector.AppHost.csproj --environment "$(ENVIRONMENT)" -o "$(OUTPUT_DIR)"
