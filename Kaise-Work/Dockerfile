# Multi-stage image: ONE process serves the FastAPI API and the built React
# SPA (src/api/spa.py). No data files are baked in — the demo CSV stays out
# (mount it read-only at data/raw/ if you have it; see README "Run with
# Docker"). Deploy targets: Render (primary), Hugging Face Spaces (fallback).

# --- Stage 1: build the React SPA -------------------------------------------
FROM node:22-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
COPY frontend/src ./src
RUN npm run build

# --- Stage 2: uv binary (pinned; version matches local `uv --version` that
# --- maintains uv.lock) -------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.13.1 AS uv

# --- Stage 3: Python 3.12 runtime (uv, frozen lockfile) ----------------------
FROM python:3.12-slim
# Python 3.12 satisfies requires-python ">=3.12,<3.15" in pyproject.toml.
COPY --from=uv /uv /usr/local/bin/uv
# Use the interpreter shipped with the base image; never download another.
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev
COPY --from=frontend-build /build/dist ./frontend/dist
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
# $PORT is provided by the platform (Render); defaults to 8000 locally.
# `exec` forwards SIGTERM to uvicorn (fast, clean container shutdown).
CMD ["sh", "-c", "exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
