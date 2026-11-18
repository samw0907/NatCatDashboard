# NatCatDashboard

A live monitoring and prioritisation tool for US natural catastrophe events —
earthquake, tropical cyclone (wind), and wildfire. Polls open hazard feeds,
enriches each live event with an estimate of what is exposed underneath it, scores
it on two independent axes (humanitarian and economic), and ranks it. Selecting an
event will trigger an on-demand building footprint analysis that reports a *range*
of counts with source disagreement made explicit, rather than a single number.

A portfolio project demonstrating the triage-to-delivery workflow of a NatCat
operations analyst role in commercial Earth observation and insurance analytics —
**not an operational emergency response tool.**

**Live app**: not yet deployed (no real frontend yet)
**API**: https://natcatdashboard-production.up.railway.app (FastAPI on Railway;
interactive docs at `/docs`)

## Why this exists

Full reasoning in [`NATCAT_TRIAGE_PROJECT_PLAN.md`](NATCAT_TRIAGE_PROJECT_PLAN.md) —
this is the document to read first. In short: the core of NatCat operations work is
judgment under ambiguity — deciding which live events matter most and why — rather
than image processing. This project replicates that triage-to-delivery cycle from open
data, rather than adding another SAR change-detection project to an already SAR-heavy
portfolio.

This project deliberately does not touch satellite imagery. It measures *exposure*
(what's underneath a hazard footprint), never *damage* or *impact* — that distinction
is the boundary against the separate SAR projects in this portfolio.

## What this is NOT

See [`NATCAT_TRIAGE_PROJECT_PLAN.md`](NATCAT_TRIAGE_PROJECT_PLAN.md) section 3 for the
full list. Headlines: not damage assessment, not a SAR project, not global (US only),
not flood, not a historical archive, not an SLA simulator, not an engineering showcase.

## Architecture

- **Backend**: FastAPI + SQLAlchemy + Alembic, Python. One raw table per source (USGS,
  NHC storms, NHC RSS, NIFC, GDACS) and one normalised `events` table. A
  `building_analysis` cache table is planned for Phase 4 and does not exist yet.
  Deployed on Railway.
- **Database**: plain Postgres on Railway (no PostGIS). Geometry is stored as GeoJSON
  and processed with shapely — see `DECISIONS.md`.
- **Frontend**: React + TypeScript + Vite + maplibre-gl, currently a placeholder page
  that calls `/health`. Map plus ranked, sortable, filterable table is planned;
  deployment to S3 + CloudFront is planned.

This mirrors the existing [`WildfireDashboard`](../WildfireDashboard) project's stack.

## Data sources

| Peril | Source |
|---|---|
| Earthquake | USGS (event feed + PAGER loss/MMI exposure + ShakeMap MMI contour) |
| Wind (tropical cyclone) | NHC (`CurrentStorms.json` + per-basin RSS, current wind radii shapefile) |
| Wildfire | NIFC WFIGS (current interagency perimeters) |
| Economic and population exposure | USACE/FEMA National Structure Inventory (NSI) |
| Buildings (on-demand, per event, not yet built) | VIDA merged footprints (Microsoft + OSM in the US) |
| Stored, not used | GDACS (raw table only — see plan section 5.4) |

Full source detail, verification status, and known API traps: plan section 5.

## Scoring

Two axes, kept separate and visible; `overall_score` is the higher of the two.

- **Humanitarian**: population exposed, on a log scale where 10,000 people scores 50.
  Earthquake uses PAGER's MMI-banded exposure weighted by intensity; wildfire and wind
  use NSI population inside the hazard footprint.
- **Economic**: NSI structure + content replacement cost inside the footprint, on a log
  scale where the PCS US catastrophe threshold of $25M scores 50. This is replacement
  cost, not insured value.
- Every score carries a confidence string; events with no usable data stay unscored
  rather than being given a fabricated number.

Details in `scoring.py` and plan section 6.

## API

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `GET /api/events` | Unified events, ranked by overall score (nulls last) |
| `POST /api/ingest/usgs` `nifc` `nhc` `gdacs` | Fetch, store, normalise and score one source. Manual trigger; nothing is scheduled yet |
| `POST /api/prune` | Rolling-window pruning. `dry_run=true` by default; deletion only when passed `false` |

## Status

Backend pipeline complete through scoring; no frontend, building analysis or
scheduling yet.

- **Done**: Phase 0 (source verification), Phase 1 (earthquake slice), Phase 2 (NIFC,
  NHC, GDACS), Phase 3 (scoring on both axes for all three perils), rolling-window
  pruning.
- **Not started**: Phase 4 (on-demand building footprint analysis), Phase 5
  (frontend and deployment), Phase 6 (write-up).
- **In progress**: refreshing the live data after a gap in polling (ingest done; prune
  and rescoring pending).
- **Known gaps**: no scheduled polling (ingest is a manual POST); pruning is manual;
  no automated tests yet; US bounding box misses the westernmost Aleutians.

See [`PROGRESS.md`](PROGRESS.md) for the current handoff and build checklist, and
[`DECISIONS.md`](DECISIONS.md) for the reasoning behind anything that involved a real
choice.

## Local development

Requires a Postgres `DATABASE_URL` (or `DATABASE_PUBLIC_URL`) in a `.env` file at the
repo root; there is no example file. Point it at a database you're happy to modify:
`alembic upgrade head`, the ingest endpoints and `POST /api/prune` all write to it.

```
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate      # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Further reading

- [`CLAUDE.md`](CLAUDE.md) — working rules and orientation for Claude Code sessions
- [`NATCAT_TRIAGE_PROJECT_PLAN.md`](NATCAT_TRIAGE_PROJECT_PLAN.md) — the plan, read
  this first
- [`NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md`](NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md)
  — the research behind the plan, useful for the eventual write-up
- [`NatCat_Data_Reliability_Reference.md`](NatCat_Data_Reliability_Reference.md) —
  failure modes for population, elevation and road data, the QC standard for this
  project
- [`DECISIONS.md`](DECISIONS.md) — the "why" behind real choices, kept separate from
  the day-to-day build checklist
- [`PROGRESS.md`](PROGRESS.md) — current handoff plus the running build checklist
