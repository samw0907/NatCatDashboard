# NatCatDashboard — Build Progress

The handoff section below is the current state of the project, written for a fresh
session that has never seen a previous conversation. Update it at the end of every
session. The build history further down is the detailed record of how it got here.
See `DECISIONS.md` for the reasoning behind real choices and
`NATCAT_TRIAGE_PROJECT_PLAN.md` for the plan itself.

---

## Handoff - current state (updated 2026-11-18)

### Where the project is
The backend pipeline is complete through scoring for all three perils. There is no
real frontend, no building footprint analysis, no scheduled polling and no write-up yet.

- **Phase 0** (source verification): done 2026-08-23. Findings are in `DECISIONS.md`.
- **Phase 1** (earthquake vertical slice): done, apart from frontend wiring, which was
  deliberately deferred so the frontend is built once against all three perils.
- **Phase 2** (NIFC wildfire, NHC wind, GDACS raw-only): done.
- **Phase 3** (scoring on both axes for all three perils): done.
- **Rolling-window pruning**: built. It is a manual trigger, not automatic.
- **Security hardening and cloud readiness** (2026-11-18): token-gated write
  endpoints, local data CLI, pinned dependencies, offline test suite, CI. Done.
- **Phase 4** (on-demand building footprint drill-down, `building_analysis` table): not started.
- **Phase 5** (map + ranked table + event detail, deploy frontend to S3/CloudFront): not started.
- **Phase 6** (write-up): not started.

### Infrastructure and security (updated 2026-11-18)
- Railway backend: https://natcatdashboard-production.up.railway.app. Railway Postgres
  is reachable. Alembic is at head (`71614cfed4d5`), in sync with the code.
- **Write endpoints are now token-gated** (`backend/app/auth.py`, merged 2026-11-18).
  `POST /api/ingest/*` and `POST /api/prune` need `X-Admin-Token` matching
  `ADMIN_TOKEN`; without a configured token they return 503 (fail closed). Read
  endpoints stay public. Until Sam sets `ADMIN_TOKEN` on Railway, the live write
  endpoints are simply disabled, which is the safe state. See "Needs doing locally".
- CORS allows only `GET`. Dependencies are pinned in `backend/requirements.txt`.
- Tests: 43 passing (`cd backend && python -m pytest -q`), fully offline against
  `backend/tests/fixtures/` and in-memory SQLite. CI (`.github/workflows/ci.yml`) runs
  them plus frontend lint and build and a gitleaks secret scan on every PR and push to
  `main`.
- Data operations from Sam's machine: `python -m app.cli` (see `CLAUDE.md`).
- Local development points at the **Railway production database** via
  `DATABASE_PUBLIC_URL` in `.env`. There is no separate dev database. `.env` is local
  only and has never been committed.
- No AWS resources exist for this project yet. Anything visible in AWS belongs to
  WildfireDashboard.
- Git history was rewritten once (2026-11-18) to make the repo standalone. See
  `DECISIONS.md`. Any other clone made before that date should be re-cloned, not pulled.

### Live backend status (checked 2026-11-18, 16:04 UTC) - needs attention
- The deployed backend is **still running the pre-auth code**. Its `/openapi.json` has
  no `X-Admin-Token` parameter, so the push of `3591f29` to `main` did not trigger a
  Railway deploy, or the deploy has not finished. Find out whether the backend service
  deploys from GitHub automatically or was deployed some other way.
- **Every database-backed endpoint returns 500**, including the public
  `GET /api/events`. `/health` (no database) returns 200. The local `.env` credentials
  still connect fine (`alembic current` works), so the database itself is up. The most
  likely cause is the deployed service holding stale database credentials, for example
  after the password rotation. A redeploy, which re-reads Railway's variable
  references, should fix it. Check the Railway deploy logs if not.
- CI on GitHub passed for `3591f29` (tests on Python 3.13, frontend build, secret scan).

### Needs doing locally (Sam, at home) - in this order
Cloud sessions cannot do any of these. Each one is marked done here once finished.
0. **Redeploy the Railway backend from the latest `main`** (see "Live backend status"
   above), ideally after setting `ADMIN_TOKEN` (items 1-2), so a single redeploy
   picks up the new code, the token and fresh database credentials together.
1. **Create the admin token.** Run this yourself and don't paste the output into any
   chat: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. **Railway:** add it as `ADMIN_TOKEN` in the backend service's Variables. This
   triggers a redeploy. Also check that the deploy built successfully with the newly
   pinned `requirements.txt`. If the build fails, Railway keeps serving the previous,
   unprotected version, so this check matters.
3. **Check the live endpoints are protected:**
   `curl -i -X POST https://natcatdashboard-production.up.railway.app/api/prune`
   should return 401 (or 503 if the token isn't set yet). A 200 means old code is still
   live (a dry run, so nothing is deleted); check the Railway deploy logs.
4. **Finish the Postgres password rotation** (in progress). Then put the new
   `DATABASE_PUBLIC_URL` in the local `.env`, confirm
   `GET https://natcatdashboard-production.up.railway.app/api/events` still returns
   200 (redeploy the backend if not), and tell Claude the date so it can be logged in
   `DECISIONS.md`. Also add `ADMIN_TOKEN` to the local `.env` if you want to call the
   API's write endpoints; the CLI doesn't need it.
5. **GitHub repo settings:** enable Secret scanning and Push protection (Settings >
   Code security). Add a ruleset on `main` that blocks force pushes and deletion.
   Requiring PRs is optional: local sessions push to `main` directly, so a "require a
   PR" rule would also block those.
6. **Claude Code cloud environment:** give the Claude GitHub app access to this repo.
   Allow network access to the package registries (PyPI, npm) so sessions can install
   dependencies. Add **no** environment variables or secrets to the cloud environment.
   Setup commands: `cd backend && pip install -r requirements-dev.txt` and
   `cd frontend && npm ci`.
7. **Data refresh.** It writes to production; Claude needs explicit approval, or run it
   yourself from `backend/` with the venv active:
   - `python -m app.cli ingest all --score-limit 0`. Re-ingest first: presence-based
     pruning reads the last poll time, so pruning on a stale poll would wrongly delete
     still-active wildfires.
   - `python -m app.cli prune`. A dry run. Sanity-check the counts: only rows older
     than 14 days (USGS/GDACS), or absent from today's feed (NIFC/NHC).
   - `python -m app.cli prune --execute`
   - `python -m app.cli score nifc --limit 20`, repeated until `remaining` is 0
     (about 30 seconds per fire), then `score usgs` and `score nhc`.
8. When happy with the history rewrite, delete the local backup
   `C:\Users\swill\dev\NatCatDashboard-pre-rewrite.bundle`. It contains the old wording.

### Last known data state (2026-11-14)
Ingest on 2026-11-14 brought in 403 earthquakes (9 PAGER-enriched), 40 current
wildfires, 0 storms (off-season) and 1 GDACS record, alongside the stale August rows.
A prune dry run then reconciled exactly: it would remove 346 USGS rows (the August
set), 199 NIFC (217 August fires minus 18 still burning), 1 NHC storm plus 7 RSS items,
and 5 GDACS rows. The real prune has **not** run yet. Item 7 above re-does this from a
fresh ingest.

### Open decisions (plan section 12)
| # | Status |
|---|---|
| O1 rolling window | Resolved 2026-08-28: 14 days by age for USGS/GDACS; by presence (3 days wildfire, 2 days wind) |
| O2 poll frequency | **Open.** Nothing is scheduled; every ingest is a manual trigger. A scheduler would call the token-gated endpoints or the CLI |
| O3 enrichment screening | Resolved: fetch PAGER/ShakeMap only when USGS `alert` is non-null |
| O4 humanitarian formulation | Resolved 2026-08-25: log scale, 10,000 people exposed = 50 |
| O5 economic formulation | Resolved 2026-08-25: log scale, PCS $25M = 50, NSI replacement cost. Occupancy-mix weighting not used |
| O6 population source | Resolved: PAGER for earthquake, NSI daytime population for wildfire/wind |
| O7 confidence display | **Open.** Confidence is currently a free-text string per event |
| O8 building source (VIDA vs OpenBuildingMap) | **Open.** Blocks Phase 4 |
| O9 FIRMS for new fires | **Open** |
| O10 database technology | Resolved: plain Postgres + shapely, no PostGIS |
| O11 stack/hosting | Resolved: backend on Railway; frontend on S3 + CloudFront (planned, not provisioned) |
| O12 repo name/structure | Resolved: `NatCatDashboard`, flat `backend/` + `frontend/` |
| O13 plain-language summary | **Open.** Phase 5 |
| O14 use of GDACS data | **Deferred.** Data accumulates in the raw table |
| O15 back-fill/retain older data if live data is thin | **Open, raised 2026-11-14.** Live data stays primary. Decide after the refresh shows what live data looks like and after checking what history each source holds |

### Known issues
- No scheduled polling, and pruning is manual (O2).
- USGS ingest took about 7 minutes from a local machine, mostly per-row
  `session.get`/`merge` round trips over the public Railway proxy. `GET /api/events`
  returns every row with no pagination, and takes about 8 seconds locally.
- A footprint with zero exposure scores `None`, not 0, because the log scale is
  undefined at 0 (pinned by a test in `test_scoring.py`). "NSI intersection, 0
  structures found" events therefore rank alongside genuinely unscored ones. This is a
  design question for Sam (related to O7), not a bug to fix silently.
- Some old rows still carry confidence strings from earlier code (e.g. "not yet scored
  (Phase 3)"). They clear once the prune runs.
- NSI bbox queries for very large wildfires (70,000+ acres) are untested at scale and
  may hit the 60-second timeout.
- NHC `event_time` is the first time a storm was seen by our poll, not storm genesis.
- The USGS US bounding box misses the westernmost Aleutians (antimeridian).
- The NSI licensing position for redistribution (not read access) is not fully resolved.
- The Railway Postgres password rotation is in progress (local item 4).
- There is no `.env.example`, by design. The required variable names are in `CLAUDE.md`.

### Next 3 tasks (all cloud-friendly)
1. **Phase 5 backend:** add sorting by axis (`humanitarian`/`economic`/`overall`) and
   a peril filter to `GET /api/events` (plan section 8.3). Add a single-event detail
   endpoint returning the footprint and score breakdown, keeping the list endpoint
   light (no footprints in the list). Tests in `backend/tests/` against SQLite.
2. **Phase 5 frontend:** ranked, sortable table plus a maplibre map reading
   `GET /api/events`. For offline development, add a small saved sample of the API's
   output as a frontend fixture, and keep the API base URL configurable.
3. **Decisions to put to Sam, not build:** present options with pros and cons for
   O15 (whether and how to supplement thin live data, after checking what history each
   source serves) and for how zero-exposure events should rank and display (O7).
   Record the options in the plan's section 12 and wait for Sam's choice.

---

## Build history

## Planning
- [x] Full project plan reviewed (`NATCAT_TRIAGE_PROJECT_PLAN.md`,
      `NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md`, `NatCat_Data_Reliability_Reference.md`)
- [x] Stack decided: mirror WildfireDashboard (FastAPI/SQLAlchemy/Alembic/Postgres on
      Railway; React/Vite/TS/maplibre-gl on S3+CloudFront)
- [x] Repo layout decided: flat `/backend` + `/frontend`, mirroring WildfireDashboard
- [x] No authentication for now (public read-only dashboard, no admin actions planned)
- [x] Git policy: originally Sam ran all git commands manually. Superseded
      2026-11-18: Claude now commits and pushes (see `CLAUDE.md` working rules and
      `DECISIONS.md`)

## Repo setup
- [x] `dev/NatCatDashboard` folder confirmed empty, not yet a git repo
- [x] `.gitignore` scaffolded (secrets, Python, Node, OS/editor, logs). Planning docs
      were originally ignored (local only); since 2026-11-18 they are tracked so cloud
      sessions can read them
- [x] Planning docs copied into repo root
- [x] `README.md`, `DECISIONS.md`, `PROGRESS.md` written
- [x] `.env.example` scaffolded (placeholders only; later deleted by choice)
- [x] `git init` + first commit + GitHub remote + push (Sam, manually) -
      `github.com/samw0907/NatCatDashboard`

## Backend core
- [x] FastAPI skeleton + `/health` endpoint + `requirements.txt`
      (`backend/app/main.py`, `backend/app/config.py`)
- [x] Local `.venv` created, dependencies installed, verified boots in-process
      (`/health` returns `{"status": "ok"}`)
- [x] Alembic skeleton generated, wired to `Settings.sqlalchemy_database_url`
      (`backend/migrations/env.py`), no models or migrations yet (Phase 1)
- [x] `Procfile` added for Railway deploy (`web: uvicorn app.main:app ...`)
- [x] Railway project + Postgres service provisioned (Sam, manually) - see Railway
      deployment section below
- [x] Database technology decision (O10): plain Postgres + shapely, not PostGIS - see
      `DECISIONS.md` and plan section 8.1

## Frontend core
- [x] Vite + React + TypeScript scaffold (`npm create vite@latest -- --template
      react-ts`), matching WildfireDashboard's toolchain (oxlint, same Vite/TS majors)
- [x] `maplibre-gl`, `react-router-dom`, `@types/geojson` added
- [x] Default counter-demo content replaced with a minimal placeholder page that
      calls the backend `/health` endpoint and imports maplibre-gl's CSS
- [x] Verified `npm run build` compiles and bundles cleanly
- [ ] AWS S3 bucket + CloudFront distribution provisioned (Sam, manually, when ready
      to deploy - not needed until Phase 5)

## Railway deployment (done, 2026-08-25)
- [x] Postgres service provisioned, public TCP proxy enabled for local dev access
- [x] Backend deployed as a second service in the same Railway project, root directory
      set to `backend`, Nixpacks auto-detected Python + read `Procfile` for the start
      command, no Dockerfile needed
- [x] `DATABASE_URL` wired via Railway variable reference to the Postgres service
      (not a static copy - stays in sync automatically)
- [x] `CORS_ALLOWED_ORIGINS` set to `http://localhost:5173` (placeholder until the
      frontend is deployed)
- [x] Public domain generated: https://natcatdashboard-production.up.railway.app
- [x] Verified live: `/health` returns 200, and `POST /api/ingest/usgs` successfully
      reached Postgres via the internal `DATABASE_URL` reference and produced the same
      counts as the local run (392 fetched, 4 enriched) - confirms the deployed
      backend can actually talk to the database, not just that it boots

## Phase 0 - Verification (done, 2026-08-23)
Full findings in `DECISIONS.md` ("Phase 0 verification findings"). Headlines:
- [x] USGS summary feed + single-event product fetch - confirmed, cleaner than
      expected (direct JSON exposure/loss endpoints, no PDF scraping needed)
- [x] NHC - real feeds are per-basin `.xml`, not `gis/rss.php` (a landing page).
      Found a better source not in the plan: `CurrentStorms.json`
- [x] NIFC WFIGS - re-confirmed live
- [x] VIDA dataset - confirmed live, keyless, FlatGeobuf by-country. Confidence field
      survives the merge but **zero Google-sourced rows in the US** - the confidence
      filter doesn't apply to this project's scope
- [x] GDACS SEARCH endpoint - confirmed live, no special headers needed (earlier 400
      was a tool artefact)
- [x] GDACS wildfire threshold claim - **correction needed**: GDACS actually flagged
      the LA wildfires (Orange), it didn't miss them. Real finding: it never escalated
      past Orange despite being the costliest wildfire on record - a metric mismatch
      (hectares vs. structure value), not a missed event. Plan sections 4.5/5.4/10
      need updating to reflect this
- [x] NSI - API root, live bbox query (polygon-ring format, not simple bbox),
      2026 vintage confirmed (population Apr 2025, prices Aug 2025), day/night
      over/under-65 population confirmed live
- [x] Population layer for O6 - not fully tested, but WorldPop's hosted API has a
      documented reliability problem from WildfireDashboard's own prior experience;
      leans toward using NSI's own day/night figures instead of a separate product

## Post-Phase-0 design discussion (done, 2026-08-23)
- [x] Building footprint methodology confirmed already settled (plan 7.4) - four
      parallel counts + disagreement classification, no single primary source
- [x] NHC ingest: build both RSS feeds and `CurrentStorms.json`, decide later which
      (if either) to drop - same demote-don't-delete logic as GDACS
- [x] O6 (population source) resolved: earthquake uses PAGER's own LandScan-based
      exposure; wildfire/wind use NSI's single population figure, no day/night switch.
      Verified against a real rural area (Arthur County, NE) that NSI's point-based
      structure avoids WildfireDashboard's Census-tract flat-rate problem
- [x] O10 (database technology) resolved: plain Postgres + shapely, not PostGIS

## Phase 1 - earthquake-only vertical slice (backend done, 2026-08-25; frontend wiring still open)
- [x] `raw_usgs_events` model (`backend/app/models.py`) - shaped to USGS's own
      summary-feed + losspager structure, full raw properties JSON kept for fidelity
- [x] Ingest logic (`backend/app/usgs.py`): fetch (US bbox, min mag 2.5, `query`
      endpoint since scoping to the US needs geographic filtering the pre-built feeds
      don't offer), two-tier PAGER enrichment (screening threshold = `alert` non-null,
      borrowing PAGER's own judgment rather than inventing a magnitude cutoff - O3
      resolved this way), idempotent upsert that never clobbers existing enrichment
      on a failed/skipped re-fetch
- [x] `POST /api/ingest/usgs` endpoint (`backend/app/routers/ingest.py`) wired into
      `main.py` - confirmed app still boots and `/health` still passes with it included
- [x] `backend/app/db.py`: lazy engine creation (deviates from WildfireDashboard's
      module-level engine deliberately - keeps the app importable/testable before
      Railway Postgres exists)
- [x] End-to-end smoke test against **live USGS data** using a throwaway local SQLite
      stand-in (`verification/test_usgs_ingest.py`, gitignored): 398 real US events
      fetched, 5 correctly enriched with PAGER data, idempotent re-poll confirmed
      (stable row count, enrichment preserved, `first_seen_at`/`last_polled_at`
      behaving correctly)
- [x] Alembic migration for `raw_usgs_events` generated and applied to the real
      Railway Postgres. Caught and fixed a real bug along the way: `migrations/env.py`
      had a placeholder comment for importing `app.models` that was never activated,
      so the first autogenerate came back empty (no tables detected) - fixed by
      actually importing the module rather than just leaving a comment about it
- [x] Verified against the **real deployed database**, not just local SQLite: ingest
      run directly against Railway Postgres (392 fetched, 4 enriched), then verified
      again by hitting the live `POST /api/ingest/usgs` on the deployed backend itself
      (same counts) - confirms the deployed service can actually reach the database
      via the internal `DATABASE_URL` reference, not just that it boots
- [x] `Event` unified table (`backend/app/models.py`) + `normalize_to_events()`
      (`backend/app/usgs.py`) - maps raw USGS rows into the peril-agnostic shape every
      source will eventually write into. One deliberate gap, not an oversight: no real
      footprint geometry yet for earthquake (would need USGS's ShakeMap MMI contours,
      not fetched yet) - left null rather than approximated with an invented radius,
      deferred to Phase 3 when NSI point-in-polygon intersection actually needs it
- [x] `POST /api/ingest/usgs` now runs normalisation immediately after raw ingest
      (matches plan section 8.2's ingest step ordering)
- [x] `GET /api/events` added (`backend/app/routers/events.py`), now ordered by
      `overall_score` (nulls last) - proves the pipeline produces an actual ranked
      queue, not just a normalised table. Sorting by a chosen axis and peril
      filtering (section 8.3) still Phase 5
- [x] Migration for `events` generated and applied to Railway Postgres, reviewed
      before applying (straightforward `CREATE TABLE`, nothing destructive)
- [x] First (simple) scoring pass (`_score_from_pager` in `usgs.py`), wired into
      `normalize_to_events()`. Deliberately thin, not the real O4/O5 formulation:
      bands PAGER's own already-published fatality and economic-loss numbers using
      PAGER's own thresholds (yellow/orange/red at 1/100/1000 deaths and
      $1M/$100M/$1B), kept as genuinely separate humanitarian/economic axes per plan
      section 6.2 rather than duplicating the single combined `alert` colour into
      both, `overall_score` = max of the two per the plan's max rule. Only scores the
      minority of events with a PAGER product - everything else stays null with an
      honest confidence string ("no PAGER product available") rather than a
      fabricated number, matching section 6.3's confidence requirement. The real
      formulation, scoring every event (not just PAGER-covered ones) via NSI, is
      still Phase 3 - this only proves the scoring plumbing works end-to-end
- [ ] Wire real earthquake data into the placeholder frontend page - deliberately
      deferred (see 2026-08-25 decision below): building the frontend once against
      multi-peril data makes more sense than building and revising it per peril

## Phase 2 - remaining perils (complete, 2026-08-25)
- [x] **Frontend-wiring decision:** hold off on any frontend work until more perils
      are flowing, rather than wire earthquake now and revisit twice more. Sam's call,
      made explicitly rather than assumed
- [x] `raw_nifc_events` model (`backend/app/models.py`) - shaped to WFIGS's own field
      structure, full raw properties JSON kept for fidelity (same pattern as USGS)
- [x] Ingest logic (`backend/app/nifc.py`): re-verified the `WFIGS_Interagency_
      Perimeters_Current` endpoint live before building against it (previously
      verified by `WildfireDashboard` 2026-07-28, and again in this project's Phase
      0). No US geographic filtering needed - WFIGS is inherently a US interagency
      system, unlike USGS's global feed
- [x] `normalize_to_events()` for NIFC - **wildfire gets a real footprint polygon
      from day one**, unlike earthquake's still-null geometry. Centroid computed via
      shapely for the point lon/lat, full perimeter polygon stored in
      `footprint_geojson`. Uses `poly_GISAcres` (calculated from the actual stored
      perimeter) as the primary metric rather than the self-reported
      `attr_IncidentSize`, since the two can diverge and GIS acres stays internally
      consistent with the geometry also being stored
- [x] Scoring deliberately left null for wildfire (`confidence: "not yet scored
      (Phase 3)"`) rather than inventing a second one-off placeholder scheme the way
      Phase 1(d) did for earthquake's PAGER data - the real formulation is Phase 3's
      job, done once, uniformly, for every peril via NSI
- [x] `POST /api/ingest/nifc` added, migration generated (correctly detected this
      time - the env.py import fix is holding), reviewed, and applied to Railway
      Postgres
- [x] Verified against **live NIFC data and the real database**: 217 wildfires
      ingested and normalised, zero skipped records, real centroid coordinates
      computed from real perimeter polygons. Unified `events` table now holds 609
      rows across two perils (392 earthquake + 217 wildfire) - confirms the
      normalisation design genuinely generalises across sources, which is exactly
      what Phase 2 is meant to test (plan section 9)
- [x] NHC ingest (wind) - both `CurrentStorms.json` and the three per-basin RSS feeds
      (at/ep/cp) built, per the 2026-08-23 "ingest both, decide later" decision. Real
      data confirmed this was the right call, not just caution: `CurrentStorms.json`
      kept tracking a storm (Moke) as "PTC" - post-tropical cyclone - status, while
      the RSS feed's headline for the same storm called it the "final advisory" -
      genuinely different information, not redundant views of the same thing
- [x] `raw_nhc_storms` (from `CurrentStorms.json`, normalised into `events`, peril
      `wind`) + `raw_nhc_rss_items` (from RSS, stored only - not normalised, since
      these are product announcements/headlines rather than events in their own
      right). RSS's `<nhc:Cyclone>` summary items parsed into a `cyclone_data` JSON
      field - captures a human-readable NHC headline `CurrentStorms.json` has no
      equivalent for at all (e.g. "MOKE IS NO LONGER A TROPICAL CYCLONE... THIS IS
      THE FINAL NHC ADVISORY")
- [x] `POST /api/ingest/nhc` added, running both ingests plus normalisation.
      Migration for both new tables generated (correctly detected), reviewed, applied
- [x] Verified against **live NHC data and the real database**: 4 active storms
      (Iselle, Julio, Lala, Moke) correctly normalised with real position/intensity,
      29 RSS items stored across all three basins, zero parse failures. Unified
      `events` table now holds 613 rows across all three perils (392 earthquake +
      217 wildfire + 4 wind)
- [x] GDACS ingest (`backend/app/gdacs.py`) - raw table only, scoped to the three
      perils this project tracks (EQ, TC, WF) rather than all seven GDACS hazard
      types, global rather than US-filtered (GDACS's SEARCH endpoint offers no
      geographic filter, and filtering client-side would be premature before O14
      decides what, if anything, this data gets used for). Keyed on
      `(event_id, episode_id)` so repeated polls naturally accumulate episode
      history rather than only keeping latest state. `POST /api/ingest/gdacs` added,
      migration reviewed and applied
- [x] Verified against **live GDACS data and the real database**: 5 events (EQ/TC/WF
      combined) fetched and stored, zero skipped - and confirmed the unified
      `events` table stayed at exactly 613 rows, completely untouched, proving the
      raw-only/never-normalised design actually holds in practice, not just on paper

**Phase 2 complete** (2026-08-25) - all three remaining perils (NIFC, NHC, GDACS)
built and verified against live data and the real deployed database.
- [x] (Resolved: the deployed backend now runs the latest `main`, confirmed 2026-11-14.) Was: deployed backend still running pre-Phase-2 code until pushed - `/api/events`
      on the live URL won't show wildfire or wind yet

## Phase 3 - real scoring formulation (O4/O5 resolved, 2026-08-25)
Three design decisions confirmed with Sam before writing any code (plan rule 1 -
no significant methodology decision made unilaterally): score what's ready now
rather than block on fetching earthquake/wind footprint geometry first; continuous
log-scale scoring rather than banded/ordinal; economic axis anchored to PCS's real
$25M threshold.
- [x] `backend/app/scoring.py` - shared log-scale score (`value == reference` maps
      to 50, two orders of magnitude above maps to 100, two below maps to 0).
      Humanitarian axis anchored to **10,000 population exposed** - GDACS's own
      wildfire homepage-display threshold (plan section 5.4), the only real
      published "this matters" population-exposure reference point found during
      research, generalised across perils as a stated assumption. Economic axis
      anchored to **PCS's $25M** US catastrophe-designation threshold (section 4.1).
      `overall_score` = max of the two (D11's existing max rule, unchanged)
- [x] `backend/app/nsi.py` - fetches structures within a footprint via a two-step
      query: cheap bounding-box request to NSI's API, then precise point-in-polygon
      filtering locally via shapely - sending a real multi-thousand-point wildfire
      perimeter directly as NSI's polygon-ring parameter isn't practical. Population
      uses NSI's PM (daytime) figures per O6's single-figure resolution
- [x] **Earthquake real scoring** (`usgs.py`, replaces Phase 1(d)'s placeholder):
      humanitarian axis from PAGER's own MMI-banded population exposure, weighted
      by intensity (MMI 4+ only, weight = mmi-3) - cheap, reuses already-fetched
      data, runs on every normalisation pass. Economic axis stays null - no
      footprint geometry yet (ShakeMap contour not fetched) - deliberately deferred
      per the sequencing decision, not forgotten
- [x] **Wildfire real scoring** (`nifc.py`, new `score_events()`) - genuinely
      expensive-tier (NSI intersection), kept separate from normalisation and
      guarded: only (re)scores an event that's never been scored or whose perimeter
      has changed since it last was (`scored_at` vs `last_updated`), capped at
      `limit` (default 20) per call so no single poll runs unboundedly. Caught and
      fixed a real bug while building this: `normalize_to_events()` was
      unconditionally resetting scores to null on every poll, which would have
      wiped out anything the scoring pass computed - fixed to preserve existing
      scores during normalisation
- [x] Wind scoring deliberately not built - no footprint geometry, nothing to score
      against yet, consistent with the agreed sequencing
- [x] Verified against **live data and the real database**: earthquake scoring
      shows the continuous scale's actual point - a M3.84 quake near dense San
      Leandro/Bay Area population scored *highest* (98.7) of four live events,
      above a M5.2 quake in sparse rural Hawaii (38.1) - because the humanitarian
      axis measures population exposed, not magnitude, exactly the point section
      4.5's Myanmar/Thailand argument makes generalised to a live result. Scores
      also spread out meaningfully (98.7/38.1/10.8/0.0) rather than clumping the
      way the old banded placeholder did (all four scored identically). Wildfire
      scoring tested on a small sample (2 fires, 0 failures) rather than the full
      remaining 215 - proving correctness doesn't require exhausting the batch, and
      the limit/remaining mechanism means the rest score progressively over
      subsequent polls by design, not as a gap

## Earthquake footprint geometry + economic axis (2026-08-26)
Completes earthquake's economic axis, which Phase 3 left stubbed. Uses USGS
ShakeMap's `cont_mmi.json` contour product (found by inspecting real ShakeMap
contents - not documented in the plan in this detail). Real contour data is messier
than expected: fragments aren't reliably closed rings (~2/3 closed on a real M7.4
event checked live) - only closed rings are used, unioned into a polygon
representing the area shaking at or above MMI 4.0, using the lowest available
contour level at that threshold or above since ShakeMap doesn't compute every level
for every event.
- [x] `RawUsgsEvent.mmi_contour_geojson` added, fetched alongside PAGER enrichment
      (same detail_url, one fetch shared by both rather than fetching twice) -
      `fetch_losspager_enrichment` renamed `fetch_enrichment` to reflect this
- [x] `usgs.score_economic()` - same expensive-tier/guarded pattern as wildfire's
      `score_events()`, but only ever writes economic_score/overall_score/
      confidence/scored_at - humanitarian_score is untouched, since it's already
      set correctly from PAGER's own exposure data and NSI's population figure
      would be a worse substitute, not an improvement
- [x] Migration for `mmi_contour_geojson` reviewed and applied

**Real bug found and fixed, not just a design note this time:** SQLAlchemy's JSON
column type stores Python `None` as the JSON *value* `null` by default, not SQL
`NULL` - so `Event.footprint_geojson.is_not(None)` at the SQL level matched every
earthquake row regardless of whether it had real geometry, not just the ones that
did. First real run treated all ~400 earthquakes as scoring candidates instead of
the ~4 with an actual contour, and wrote a misleading confidence message
("NSI intersection, None structures found") onto 20 events that never had a PAGER
product at all. Caught by checking actual results against expectations rather than
just trusting a 200 response - the candidate count (58) didn't match the known
PAGER-covered count (4), which is what prompted investigating. Fixed by filtering
on `footprint_geojson` in Python after fetching (matching `nifc.py`'s
`score_events()`, which never had this bug because it never filtered on a JSON
column at the SQL level to begin with), and the 20 corrupted rows were reset
directly. Re-verified: exactly 1 real candidate found and scored correctly, zero
non-PAGER events touched.

## Wind footprint geometry + scoring (2026-08-27) - all three perils now scoreable
Uses NHC's `initialWindExtent` wind radii shapefile (current radii, not the
forecast, staying consistent with earthquake/wildfire representing current state).
Real-world format detour worth remembering: tried the KMZ product first
(`initialradii...kmz`) since it looked simpler, but GDAL's KML driver returned this
layer's geometry type as "Unknown" and `pyogrio.raw.read` silently returned no
geometry at all for it - no error, just `None`. The shapefile ZIP equivalent
(`forecastWindRadiiGIS`/`initialWindExtent` turned out to be the *same URL*,
bundling both current and forecast radii together) correctly reported `Polygon`
geometry, but even then `pyogrio.raw.read`'s low-level array-based reader returned
`None` for geometry in this environment - only the higher-level
`geopandas`/`pyogrio.read_dataframe` path actually worked. `geopandas` added as a
dependency because of this, not by default preference. Also confirmed live that
GDAL's combined `/vsizip/vsicurl/` remote-read (works fine for VIDA's FlatGeobuf)
took 30+ seconds for a wind radii ZIP under 4KB - switched to a plain download to a
temp file instead, which is fast and reliable.
- [x] `RawNhcStorm.wind_radii_geojson` added, fetched for every active storm on
      every poll (not screened/guarded like earthquake or wildfire - active storm
      counts are always small, typically 0-5 globally, so the cheap-screen/
      expensive-enrich split isn't needed here)
- [x] `nhc.score_events()` scores **both** axes via NSI (unlike earthquake, wind has
      no PAGER-equivalent published humanitarian baseline) - guarded the same way as
      wildfire's `score_events()`, and filters `footprint_geojson` in Python rather
      than SQL from the start, avoiding the JSON-null trap caught in earthquake's
      `score_economic()` the day before rather than repeating it
- [x] Migration for `wind_radii_geojson` reviewed and applied
- [x] Verified against **live NHC data and the real database**: the one currently
      active storm (Lala) got a real wind radii footprint and was correctly scored
      via NSI (0 structures found - Lala is out over open Pacific, far from any US
      land, so zero is the right answer, not a failure). Three other wind events
      shown as unscored are stale rows from earlier polls no longer in NHC's active
      feed - the already-documented rolling-window pruning gap surfacing again, not
      a new issue

**All three perils can now be scored on both axes where data supports it** -
earthquake (humanitarian: PAGER: economic: NSI/ShakeMap), wildfire (both: NSI/fire
perimeter), wind (both: NSI/wind radii). Phase 3's original scope is complete.

## Rolling-window pruning (2026-08-28, done) - O1 resolved
Split by source rather than one blanket age rule (confirmed with Sam before writing
any deletion code, per the plan's explicit requirement to flag destructive routines
in detail first): **age-based** for earthquake/GDACS (14 days by event/fetch date -
both already fetched as a bounded window, so nothing currently visible could ever be
pruned prematurely); **presence-based** for wildfire/wind (not seen in a poll for a
grace period - 3 days wildfire, 2 days wind - since `event_time`/discovery date can
be old while an incident is still very much active; a large wildfire can burn for
weeks, so pruning by age there would have been a real bug, deleting still-active
incidents just because they started a while ago).
- [x] `backend/app/pruning.py` + `POST /api/prune` (`dry_run=true` by default,
      deletion only happens when explicitly passed `false`) - not wired into the
      automatic ingest endpoints yet, triggered manually only
- [x] **Safety process followed, not skipped:** ran dry-run first against the real
      database, reviewed the results together (85 USGS candidates, 0 GDACS, 0 NIFC,
      3 NHC storms + 28 RSS items), spot-checked that the counts made sense (85 of
      431 total, not nearly all - and one sampled candidate confirmed genuinely 16
      days old against a 14-day rule) before Sam explicitly approved running it for
      real
- [x] Ran for real, verified directly against the database afterward - not just
      trusting the response: row counts dropped by exactly the predicted amounts
      (431→346 USGS, 36→8 NHC RSS items), and a specific deleted row was confirmed
      actually gone from both its raw table and the unified `events` table
- [ ] Not yet wired into the automatic ingest endpoints - still a manual trigger,
      by design, until it's been run for real more than once

## Known gaps, deliberately deferred, not forgotten
- Pruning is not yet automatic (see above) - still a manual, reviewed trigger.

See `NATCAT_TRIAGE_PROJECT_PLAN.md` section 9 for the full phase plan.
