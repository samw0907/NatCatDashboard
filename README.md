# NatCatDashboard

A live monitoring and prioritisation tool for US natural catastrophe events —
earthquake, tropical cyclone (wind), and wildfire. Polls open hazard feeds on a
schedule, enriches each live event with an estimate of what is exposed underneath it,
scores it on two independent axes (humanitarian and economic), and presents a ranked
queue and map. Selecting an event triggers an on-demand building footprint analysis
that reports a *range* of counts with source disagreement made explicit, rather than a
single number.

A portfolio project demonstrating the triage-to-delivery workflow of a NatCat
operations analyst role in commercial Earth observation and insurance analytics —
**not an operational emergency response tool.**

**Live app**: not yet deployed
**API**: https://natcatdashboard-production.up.railway.app (backend only for now - no frontend deployed yet)

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

## Architecture (planned)

- **Backend**: FastAPI + SQLAlchemy + Alembic, Python. One raw table per source (USGS,
  NHC, NIFC, GDACS), one normalised `events` table, one `building_analysis` cache
  table. Deployed on Railway.
- **Frontend**: React + TypeScript + Vite + maplibre-gl. Map plus ranked, sortable,
  filterable table. Deployed to S3, served via CloudFront.
- **Database**: Postgres on Railway. Whether PostGIS is used is still open (see
  `NATCAT_TRIAGE_PROJECT_PLAN.md` open decision O10) — decided in Phase 1.

This mirrors the existing [`WildfireDashboard`](../WildfireDashboard) project's stack,
per that plan's own default: reuse what already exists unless there's a reason not to.

## Data sources

| Peril | Source |
|---|---|
| Earthquake | USGS (event feed + PAGER alert/loss/MMI exposure) |
| Wind (tropical cyclone) | NHC (track, wind radii, wind speed probabilities) |
| Wildfire | NIFC WFIGS (incident locations + perimeters) |
| Buildings (on-demand, per event) | VIDA merged footprints (Google Open Buildings + Microsoft + OSM) |
| Economic exposure | USACE/FEMA National Structure Inventory (NSI) |
| Stored, not yet used | GDACS (see plan section 5.4 for why it's deferred, not dropped) |

Full source detail, verification status, and known API traps: plan section 5.

## Status

**Planning complete. Repo scaffolded. No ingest code written yet.** Phase 0
(verification of every unconfirmed API claim in the plan) is next.

See [`PROGRESS.md`](PROGRESS.md) for the build checklist and
[`DECISIONS.md`](DECISIONS.md) for the reasoning behind anything that involved a real
choice.

## Local development

Not yet runnable end-to-end (no `.env` values wired to real infrastructure). Once
Railway Postgres exists:

```
# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate      # Windows
pip install -r requirements.txt
cp ../.env.example ../.env  # then fill in real values manually
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Further reading

- [`NATCAT_TRIAGE_PROJECT_PLAN.md`](NATCAT_TRIAGE_PROJECT_PLAN.md) — the plan, read
  this first
- [`NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md`](NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md)
  — the research behind the plan, useful for the eventual write-up
- [`NatCat_Data_Reliability_Reference.md`](NatCat_Data_Reliability_Reference.md) —
  failure modes for population, elevation and road data, the QC standard for this
  project
- [`DECISIONS.md`](DECISIONS.md) — the "why" behind real choices, kept separate from
  the day-to-day build checklist
- [`PROGRESS.md`](PROGRESS.md) — running build checklist
