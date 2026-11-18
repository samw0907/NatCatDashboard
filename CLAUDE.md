<!-- CLAUDE.md -->

# NatCatDashboard - guide for Claude sessions

A live triage and prioritisation tool for US natural catastrophe events (earthquake,
tropical cyclone wind, wildfire). It ingests open hazard feeds, estimates what is
*exposed* under each event footprint, scores each event on two separate axes
(humanitarian and economic), and ranks them. A portfolio project demonstrating the
triage-to-delivery workflow of a NatCat operations analyst role in commercial Earth
observation and insurance analytics. The reasoning is the deliverable; the code is
the evidence for it.

## Read these first, in this order

1. [`PROGRESS.md`](PROGRESS.md) - the handoff: current state, what's in progress,
   open decisions, known issues, next tasks. Start here every session.
2. [`NATCAT_TRIAGE_PROJECT_PLAN.md`](NATCAT_TRIAGE_PROJECT_PLAN.md) - the full plan and
   the reasons behind it. Sections 0, 3 (what this is NOT), 11 (rejected approaches,
   do not repeat) and 12 (open decisions) are essential before proposing anything.
3. [`DECISIONS.md`](DECISIONS.md) - choices made during the build, with reasoning,
   including the Phase 0 source-verification findings.

Optional background: [`NatCat_Data_Reliability_Reference.md`](NatCat_Data_Reliability_Reference.md)
(data failure modes, read before Phase 4 QC work) and
[`NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md`](NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md)
(research behind the plan, useful for the write-up, not needed for building).

## Working rules

- Commit and push freely, in small logical commits with clear messages.
- In cloud sessions, work on a `claude/<short-description>` branch and open a PR; Sam
  merges to `main` himself. Never force-push, never rewrite history on `main`. Railway
  may auto-deploy from `main`, so `main` must stay deployable.
- This repo is public. Never write company names, interview/application details,
  personal career info or confidential task content into any tracked file.
- Never request, store, print or commit secrets. Config comes from a local `.env`
  at the repo root (gitignored) or from Railway service variables. There is no
  `.env.example` by design. Required variable names: `DATABASE_URL` or
  `DATABASE_PUBLIC_URL` (one is required; the public one is preferred when both are
  set), plus optional `CORS_ALLOWED_ORIGINS` (default `http://localhost:5173`) and
  `ENVIRONMENT` (default `development`). The frontend reads `VITE_API_BASE_URL`
  (default `http://localhost:8000`).
- Cloud sessions may not have network access to the hazard feeds. Tests should use
  saved sample responses in `backend/tests/fixtures/` rather than live APIs.
- At the end of every session, update `PROGRESS.md` (done / in progress / next 3
  tasks) and log any real choice in `DECISIONS.md` with its reasoning. This is the
  only context that carries between sessions.
- Do not delete data, drop tables, run migrations against the Railway database, or
  change deployment config without explaining the risk and getting Sam's explicit
  go-ahead first. Note that local development currently points at the Railway
  production database (there is no separate dev database), so a local `alembic
  upgrade`, ingest or prune call touches production.
- No significant design or methodology decision is made unilaterally. Present options
  with pros and cons and let Sam decide; add new ones to the plan's section 12.

## Style

- No emojis. Plain explanations; don't bury the point in structure.
- Code comments sparingly, only where a section genuinely needs explaining, plus a
  file path comment at the top of every file.
- Language: "exposed", never "affected", "damaged" or "impacted" (plan section 6.1).
- Stay scoped to this project. Don't touch other portfolio projects' infrastructure
  (e.g. WildfireDashboard's AWS/Railway) unless asked.

## Layout

- `backend/` - FastAPI + SQLAlchemy + Alembic, Python. One module per source
  (`usgs.py`, `nifc.py`, `nhc.py`, `gdacs.py`), `nsi.py` for exposure,
  `scoring.py`, `pruning.py`, routers in `app/routers/`. Plain Postgres on Railway;
  geometry stored as GeoJSON in JSON columns, processed with shapely.
- `frontend/` - React + TypeScript + Vite + maplibre-gl. Currently a placeholder page.
- `verification/` - gitignored Phase 0 throwaway scripts and raw responses (local only).

## Commands

```
# Backend (from backend/)
python -m venv .venv && .venv/Scripts/activate   # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
uvicorn app.main:app --reload                    # needs DATABASE_URL or DATABASE_PUBLIC_URL

# Frontend (from frontend/)
npm install
npm run dev
npm run build
```

## Known traps

- A SQLAlchemy `JSON` column stores Python `None` as JSON `null`, not SQL `NULL`, so
  `.is_not(None)` on a JSON column matches every row. Filter in Python after fetching.
- If `alembic revision --autogenerate` comes back empty, check that
  `migrations/env.py` still imports `app.models`.
- Normalisation must preserve existing scores; the expensive NSI scoring passes own
  them.
