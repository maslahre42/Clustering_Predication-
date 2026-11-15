# SmartWasteRouting

Explainable glass-waste collection forecasting and route-optimisation prototype
for the PreZero / City of Heilbronn challenge. See `PLAN.md` for milestones and
`AGENTS.md` for repository rules.

## Stack

- **Backend**: Python (FastAPI, pandas/numpy, scikit-learn, OR-Tools, Pydantic), pytest, ruff, mypy (strict for `src/`).
- **Frontend**: React + TypeScript + Vite, Tailwind CSS, Recharts, Leaflet, Vitest.

## Prerequisites (verified locally)

| Tool | Version used |
|---|---|
| Python | 3.14.8 (3.11–3.14 supported; ortools has no 3.15 wheels yet, see `pyproject.toml`) |
| uv | 0.13.1 |
| Node | v26.13.0 |
| npm | 11.20.0 |

## Backend setup (uv, preferred; uv is installed)

```bash
uv venv --python 3.14          # creates .venv (use --clear to recreate)
uv pip install -e ".[dev]"     # installs runtime + dev dependencies
```

Alternative without uv (Python 3.11–3.14):

```bash
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
.venv/bin/uvicorn src.api.main:app --reload   # API on http://127.0.0.1:8000
```

## Run with Docker

One multi-stage image serves the FastAPI API and the built React SPA from a
single process (`src/api/spa.py` mounts `frontend/dist` at `/` with an SPA
fallback). No data is baked into the image.

```bash
docker build -t wasterouting .
docker run -p 8000:8000 wasterouting        # http://localhost:8000

# Optional (private CSV stays on your machine): enable the demo endpoint by
# mounting the challenge CSV read-only — it is never committed or copied:
docker run -p 8000:8000 -v "$PWD/data/raw:/app/data/raw:ro" wasterouting
```

Without the mount, `POST /api/datasets/demo` answers a friendly 404 and the
UI still works with uploaded CSVs.

### Deployment knobs (hosted environments, optional)

| Env var | Effect | Default |
|---|---|---|
| `WASTECITY_SOLVER_TIME_LIMIT_S` | Positive finite float; replaces the default `solver_time_limit_s` (§4.6) for requests that do **not** override it. An explicit request override always wins. Applies everywhere (interactive route **and** `/api/comparison`) — a pure stopping-criterion safety knob. | unset → §4.6 default |
| `WASTECITY_MAX_STOPS` | Positive int; only the first N policy-selected candidates (§3.3 order) are handed to the solver; the rest appear in `unserved` with reason `hosted_demo_stop_cap` — never silently dropped. Applies to the **interactive route demo only** (`POST /api/route`); `/api/comparison` is always computed on the full §4.7 basis so gains stay like-for-like. | unset → no cap |

Invalid values are ignored with a warning log (the service never crashes on
them); unset variables leave behaviour byte-identical to local defaults.
These are **deployment knobs of this prototype, not new assumptions about
the challenge** — responses label them `[deployment setting]`.

Example (free-tier-sized demo run):

```bash
docker run -p 8000:8000 -e WASTECITY_MAX_STOPS=50 -e WASTECITY_SOLVER_TIME_LIMIT_S=10 -v "$PWD/data/raw:/app/data/raw:ro" wasterouting
```

## Deploy

Both platforms run the image as a Docker web service; `PORT` is provided by
the platform and read by the container command.

- **Render (primary)**: create a Web Service with Docker runtime. Free-tier
  characteristics: ~1 min cold start after inactivity, **ephemeral disk**
  (uploaded datasets and demo data vanish on restart; the in-memory active
  dataset resets — re-upload or reload demo data), 512 MB RAM. Set the
  optional env knobs above (e.g. `WASTECITY_MAX_STOPS=50`) if needed.
- **Hugging Face Spaces (fallback)**: create a Docker Space from the same
  image/Repo; the same ephemeral-disk and cold-start notes apply; provide
  the port via the platform's `$PORT` convention.

Distances in the demo are haversine straight-line derived (synthetic
coordinates, labelled in every response) — never presented as road distance.

## Frontend setup & run

```bash
cd frontend
npm install        # installs dependencies per package.json / package-lock.json
npm run dev        # Vite dev server, proxies /health and /api/* to 127.0.0.1:8000
```

## Checks (same as CI, see `.github/workflows/ci.yml`)

```bash
.venv/bin/ruff check .   # lint
.venv/bin/mypy src       # strict type check for src/
.venv/bin/pytest         # backend tests
cd frontend && npm run build   # tsc --noEmit + Vite production build
cd frontend && npm test        # Vitest suite
```

## Demo

Start the backend and frontend as below, open http://localhost:5173 (the Vite
dev server answers on `localhost`, not `127.0.0.1`), and press **Load demo
data** on the Overview page — or upload
`data/raw/glass_fill_levels_anonymized_f.csv`. A guided walkthrough is in
`docs/demo_script.md`; the full guide (screens, architecture, limitations):
`docs/user_guide.md`. No API keys are required.

## Configuration

Copy `.env.example` to `.env` for app settings (host, port, log level). No API
keys are required for the core demo.

## Documentation

- `docs/user_guide.md` — user guide (deliverable 4): setup/run/test/demo, screens, architecture, limitations
- `docs/routing_methodology.md` — distance provenance, solver setup, fleet sizing, comparison design
- `docs/data_profile.md` — data dictionary / source audit
- `docs/contracts.md` — cross-module contracts (wire format authority)
- `docs/demo_numbers.md` — reproducible comparison numbers
- `docs/model_card.md` — forecast model card

## Data

`data/raw/` holds immutable challenge inputs (git-ignored). Derived data goes to
`data/derived/` (git-ignored) and must be reproducible from code.
