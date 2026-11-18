# NatCatDashboard — Design Decisions Log

Every decision here that involved real options and tradeoffs, in the order they came
up. Not a changelog of code changes — see git history for that. This is the "why",
kept separate from the day-to-day build checklist in `PROGRESS.md`, specifically so
it's easy to revisit later (for the write-up, or before touching something that was
decided for a non-obvious reason).

The full project reasoning — why this project exists, what it is and isn't, the
industry research behind the scoring design — lives in
`NATCAT_TRIAGE_PROJECT_PLAN.md` and is not duplicated here. This file only records
decisions made *during the build* that aren't already settled in that plan, plus any
place where the build diverged from the plan's assumptions.

---

## Application stack and hosting (2026-08-22, scaffolding)
**Issue:** The plan leaves this as open decision O11, noting only that reusing an
existing stack is the default unless there's a reason not to. Two real options existed:
mirror the existing `WildfireDashboard` project's stack (Railway + AWS), or move to a
more AWS-native setup (Lambda/Fargate + RDS) to consolidate hosting under one provider.
**Decision:** Mirror `WildfireDashboard` exactly — FastAPI + SQLAlchemy + Alembic +
Postgres backend on Railway; React + Vite + TypeScript + maplibre-gl frontend built and
synced to S3, served via CloudFront. Reasoning: it's a proven working setup already in
this portfolio, matches Sam's stated Railway/S3/CloudFront preference, and a pure-AWS
backend (VPC, IAM, cold starts) would be real added complexity with no functional
benefit for this project's scale.

## Repo layout (2026-08-22, scaffolding)
**Decision:** Flat layout mirroring `WildfireDashboard` — `/backend` and `/frontend`
as siblings at repo root, planning/decision/progress docs also at root. One repo, one
git history.

## Authentication (2026-08-22, scaffolding)
**Issue:** The plan doesn't mention any admin/write actions from the UI — it's
described throughout as a read-only queue-and-map view (plan section 2.3, 8.3). Whether
to add any auth at all was open.
**Decision:** No authentication for now. If a genuine need for a gated action emerges
later (e.g. a manual re-ingest trigger, or a destructive rolling-window operation that
should require confirmation beyond a UI dialog), `WildfireDashboard`'s pattern is the
precedent to reuse: a single shared secret in a request header, prompted once in the
browser, gating specific actions only — not a full login/session system. Not needed at
scaffolding time.

## Database technology — O10 resolved: plain Postgres, not PostGIS (2026-08-23)
**Issue:** Flagged as genuinely open rather than a rubber stamp of `WildfireDashboard`'s
choice, since this project has more geometry-heavy work in principle — hazard footprint
polygons across three perils, building footprint overlay and disagreement
classification (plan section 7.4), point-in-polygon NSI intersection.
**Resolution:** On closer analysis, the *local* database only ever stores a small
rolling window of event-level footprints (dozens to low hundreds of rows) — the heavy
geometry work (VIDA's billions of footprints, NSI's structure points) runs against
externally bbox-filtered API results, computed transiently in Python via shapely, with
only summary results cached locally (`building_analysis` table). PostGIS's spatial
indexing has little to actually bite on at that local scale, so the extra dependency
(GeoAlchemy2 or raw SQL) and learning curve aren't justified. Plain Postgres with
WKT/GeoJSON geometry columns and shapely for all intersection/overlay math, matching
`WildfireDashboard`. Revisit only if a real query need emerges that this can't serve.

## NHC ingest — poll both RSS and CurrentStorms.json (2026-08-23)
**Issue:** Phase 0 found `CurrentStorms.json` is a materially cleaner polling target
than the plan's originally-named RSS feeds — one call, all basins, direct product URLs.
Whether to replace the RSS-based approach outright or keep both was open.
**Decision:** Build both. Same demote-don't-delete logic already used for GDACS
(plan D8) — ingest is cheap, redundant sources can be compared once real data is
flowing, and dropping one later is easy while adding one back after committing to a
single source is a retrofit. Decide which (if either) to drop once Phase 2 ingestion
is actually running. See plan section 5.2.

## Population source — O6 resolved (2026-08-23)
**Issue:** The plan's original design assumed switching between day and night NSI
population figures based on event time-of-day, addressing the ambient-vs-residential
distinction. Also carried a real, unverified worry from `WildfireDashboard`'s own
history: Census-tract population data there produced a flat number smeared across
large, mostly-empty rural polygons, concentrated in reality into small towns.
**Decision:** Dropped the day/night switch — the precision it implies isn't real,
given these are modelled annual estimates. Use a single NSI population figure for
wildfire/wind; state ambient-vs-residential as a documented limitation instead of
engineering around it. For earthquake, no separate computation needed at all — USGS
PAGER's exposure numbers are already LandScan-based internally.
**Verified, not assumed:** queried NSI directly over Arthur County, Nebraska (one of
the least populated counties in the US) specifically to check for the
`WildfireDashboard`-style flat-rate problem. Confirmed it doesn't occur — agricultural
structures on empty land show zero population, population clusters correctly at the
actual town's buildings — because NSI is point-based (per-structure) rather than
polygon-averaged, which is a structural difference from Census-tract data, not just a
different number. See "Phase 0 verification findings" below.

## Git and secrets policy (2026-08-22, revised 2026-11-18)
**Original decision (2026-08-22):** no git command was run on Sam's behalf; every step
ended with copy-paste commands for Sam to run manually.
**Superseded 2026-11-18:** the project moved to Claude Code cloud sessions, which clone
from GitHub. Claude now commits and pushes in small logical commits; cloud sessions
work on `claude/<short-description>` branches and open PRs, and Sam merges to `main`.
No force-pushing and no history rewriting on `main`, which must stay deployable. Full
rules are in `CLAUDE.md`.
**Secrets (unchanged in spirit):** secrets are never requested, stored, printed or
committed. Config comes from environment variables. `.env` was read and edited
directly once (2026-08-25), as an explicit exception at Sam's request while fixing a
malformed Railway connection string. `.env.example` was later deleted by Sam's choice
and is deliberately not recreated; the required variable names are listed in
`CLAUDE.md`.

## Planning docs tracked in git (2026-11-18)
**Issue:** the planning, progress and decision docs were gitignored (local only), so a
cloud session cloning from GitHub would see the code but none of the reasoning.
**Decision:** track them. `.gitignore`'s secrets section was widened (key/cert files,
credential JSONs, `.aws/`, `.railway/` and so on), and data-download patterns were
added. Before the first commit, every newly tracked file was grepped for credentials
(none found) and for personal content. At Sam's direction, every tracked doc was then
rewritten neutrally: no company names, application history or confidential task
content, with design choices kept and justified on their operational merits. A rule
in `CLAUDE.md` keeps it that way. `verification/` stays ignored.

## Data refresh after a 2.5-month gap: ingest before prune, scoring deferred (2026-11-14)
**Issue:** nothing had polled since 2026-08-28. Running the prune first would have
deleted everything, including wildfires that are still active, because presence-based
pruning reads `last_polled_at`, which was stale for every row.
**Decision:** ingest every source first, so that still-active incidents get a fresh
`last_polled_at` (18 August wildfires were still in NIFC's current feed and correctly
survive the dry run). Pass `score_limit=0` so slow NSI scoring isn't spent on rows
about to be pruned. Then dry-run the prune, then run it for real only with Sam's
approval, then score.

## Phase 0 verification findings (2026-08-23)
Verified against live sources with real HTTP clients (curl, httpx, pyogrio, GDAL
`/vsicurl/`), not documentation alone. The raw responses are in `verification/`
(local only, gitignored). The plan was corrected in place where these findings
changed it. This is the consolidated record (it was previously `PHASE0_VERIFICATION.md`).

| Item | Plan assumed | Verified reality |
|---|---|---|
| GDACS + LA wildfires (Jan 2025) | Missed entirely (below the 10,000 ha threshold) | Flagged Orange on the real ignition dates (8,219 ha and 4,677 ha) via GDACS's manual-override path for urban-adjacent fires, and never escalated to Red. The finding is the metric mismatch (burned hectares vs structure value), not a missed event |
| Google confidence scores in VIDA (US) | Available as a 4th count filter | Field exists, but there are zero Google-sourced rows in the US. Google Open Buildings V3 excludes the US and Europe by design. A 28,136-building Altadena bbox was all `microsoft`/`osm`. Not applicable at this project's scope |
| NHC polling target | `gis/rss.php` with `gis-*` GUIDs | `rss.php` is a landing page. Real feeds are `/gis-at.xml`, `/gis-ep.xml`, `/gis-cp.xml`. Product files look like `AL112017_020adv_CONE.kmz`. `CurrentStorms.json` is a better source covering all basins |
| NSI bbox query | Simple `minx,miny,maxx,maxy` | A closed polygon ring `x1,y1,...,x1,y1`. Root is `nsi.sec.usace.army.mil/nsiapi/structures`, no key needed |
| NSI vintage | Feared stale (2019 release) | NSI 2026 Base: population indexed to April 2025, prices to August 2025. Fields confirmed: `val_struct`, `val_cont`, `val_vehic`, `occtype`, `num_story`, `found_type`, `pop2amo65`/`pop2amu65`/`pop2pmo65`/`pop2pmu65` |
| USGS PAGER detail | Some PDF-scraping might be needed | Direct JSON: `losspager` contents give `json/exposures.json` (population by MMI 1-10) and `json/losses.json` (fatalities, dollar loss) |
| GDACS SEARCH reachability | Uncertain (HTTP 400 in research) | Live, no special headers needed. The 400 was a research-tool artefact |
| NIFC WFIGS | Endpoint unverified | `WFIGS_Interagency_Perimeters_Current` FeatureServer confirmed live |

**NSI licensing:** current technical documentation lists Lightbox/HIFLD parcels,
Microsoft Building Footprints, FEMA USA Structures and Census as sources, with no
mention of CoreLogic. Keyless public API access is a good practical signal, but it is
not an explicit licence statement. This is still open if redistribution (rather than
read access) ever matters.

**Population layer candidates (input to O6):** WorldPop's hosted stats API was
"persistently unreliable" in WildfireDashboard's experience. LandScan needs an ORNL
account and a click-through licence. GHS-POP is freely downloadable and is what GDACS
uses. This tipped O6 toward NSI's own population fields.

**NSI rural check (O6):** a query over Arthur County, Nebraska showed agricultural
structures on empty land carrying zero population, with population clustered at the
actual town's buildings. So NSI's point-based data avoids WildfireDashboard's
Census-tract flat-rate smearing.

## Alembic autogenerate coming back empty (2026-08-25, bug caught and fixed)
**Issue:** `migrations/env.py` was scaffolded with a comment placeholder - "once
app/models.py defines tables, import it here" - back when no models existed yet. Once
`RawUsgsEvent` and later `Event` were actually added to `models.py`, that comment was
never turned into a real import. First `alembic revision --autogenerate` for each table
came back completely empty (`pass` in both `upgrade()` and `downgrade()`), because
Alembic compares against `Base.metadata`, which only knows about tables from modules
that have actually been imported - the model classes existing in a file nobody imports
doesn't register them.
**Fix:** `from app import models  # noqa: F401` added to `env.py`, migration deleted
and regenerated - correctly detected the table on the next attempt. Worth remembering
if a future migration ever comes back suspiciously empty: check this import first
before assuming the schema is actually already in sync.

## Unified events table - real footprint geometry deferred, not solved (2026-08-25)
**Issue:** The unified `events` table (plan section 8.1) needs a hazard footprint per
event to eventually support NSI point-in-polygon intersection (Phase 3) and the
building footprint drill-down (Phase 4). For earthquake, the natural footprint is
USGS's ShakeMap MMI intensity contour - not the same thing as the point epicenter
already stored, and not fetched or parsed yet.
**Decision:** `footprint_geojson` exists in the `Event` schema now (so no future
migration is needed just to add the column) but is left null for every earthquake row
for now, rather than approximated with an invented buffer radius around the epicenter,
which would be fabricating a shape not grounded in the actual hazard data. Real
ShakeMap contour fetching is deferred to Phase 3, when it's actually needed to run the
intersection - building it now would be speculative.

## SQLAlchemy JSON columns: Python None is not SQL NULL by default (2026-08-26, bug caught and fixed)
**Issue:** `Event.footprint_geojson.is_not(None)` in `usgs.score_economic()` matched
every earthquake row, not just the ones with real contour geometry - candidate count
was 58 when only 4 events had a PAGER product at all, which is what gave it away.
**Root cause:** SQLAlchemy's `JSON` column type stores a Python `None` value as the
JSON *value* `null` by default (`none_as_null` defaults to `False`), not as SQL
`NULL`. Postgres considers a column holding the JSON scalar `null` to have a value -
`IS NOT NULL` is true for it - even though reading it back deserializes to Python
`None` again, which is why nothing looked wrong until a query filtered on it directly.
Every other JSON column in this project only ever gets checked for nullness in
Python after fetching (`if raw.geometry:`, `if not footprint_geojson:` etc.), which
works fine regardless of which way it's stored - this only bit the one place that
filtered a JSON column at the SQL level.
**Fix:** Filter in Python after fetching instead (matches `nifc.py`'s
`score_events()`, which never had this bug because it was never written to filter on
a JSON column in SQL to begin with - not because anyone anticipated the issue).
20 rows had already been touched with a misleading confidence message before this
was caught; reset directly once identified.
**Worth remembering:** any future SQL-level `IS NULL`/`IS NOT NULL` filter on a JSON
column in this codebase needs the same care - either filter in Python instead, or
declare the column with `JSON(none_as_null=True)` if a genuine need for SQL-level
filtering comes up.
