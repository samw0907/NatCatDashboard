<!-- NATCAT_TRIAGE_PROJECT_PLAN.md -->

# US NatCat Live Triage and Prioritisation Tool — Project Plan

Created: 2026-08-22
Status: BUILD IN PROGRESS (Phases 0-3 done). Originally written at planning stage; current state is in PROGRESS.md.
Document version: 1 (full standalone context)

Research behind it: NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md.
Relationship to imagery (SAR) work: separate and downstream. See section 1.3.

---

## 0. How to use this document

This document is written to be handed to a fresh context — Claude Code or otherwise —
with no access to the conversation that produced it. It records not just *what* is
being built but *why*, because the reasoning is the deliverable and the code is the
evidence, not the other way round.

**Three rules that apply to anyone working on this project:**

1. **No significant design or methodology decisions are made unilaterally.** Every
   choice with a real tradeoff is presented to Sam as options with pros and cons, and
   Sam decides. Section 12 is the open-decisions register. If a decision needs making
   that is not in that register, add it and ask rather than choosing.
2. **Reasoning is a deliverable.** The final write-up explains why each choice was
   made, including the ones that turned out wrong. Capture reasoning as it happens; do
   not reconstruct it afterwards.
3. **Read section 11 before proposing anything.** It records the paths this project
   nearly went down and why each was wrong. Several of them are attractive-looking
   ideas that would have broken the project. If a proposal matches something in
   section 11, do not make it.

**Sam's working preferences.** No emojis. Code comments used sparingly, only where a
section genuinely needs explaining, plus a file path comment at the top of every file.
Flag any risk of destructive action — deleting data, dropping tables, overwriting
state — in detail and wait for a decision before proceeding. Warn when context is
running low. Keep explanations plain; do not bury the point in structure.

---

## 1. Why this project exists

### 1.1 The motivation

A portfolio project demonstrating the triage-to-delivery workflow of a NatCat operations
analyst role in commercial Earth observation and insurance analytics. The skill on show
is owned prioritisation judgment under ambiguity: several live events compete for
limited analyst time (say a wind event with an urgent customer request, two wildfires
and an earthquake), and the analyst has to state a clear, defensible position on what
comes first and why.

### 1.2 What the role actually is

The rest of this portfolio is SAR-heavy — amplitude change detection for flood and
wildfire. That work is good, but it is not the core of operational NatCat analyst
roles. Across published listings for these roles, SAR experience is a plus, not a
requirement. The recurring core responsibilities are:

- 24/7 monitoring and analysis operations for near-real-time NatCat assessment
- Monitoring and analysing diverse earth observation datasets to track live events
- Activation, verification and delivery of analysis output in accordance with SOP,
  adhering to quality standards and service level agreements
- Managing own workload and reprioritising based on changing requirements
- Quality control to detect and correct output inconsistencies
- Resolving small-scale operational issues independently

The central verbs are *activation, verification, delivery*. That is a triage-to-delivery
cycle, not an image-processing job. Prioritising competing events is not a side
question — it is the job.

### 1.3 Where this sits relative to the SAR work

This is a **new project type** in the portfolio. Imagery-based (SAR) follow-on work
is **not merged in**. It may later be linked to this tool as the downstream stage, or
kept separate; either way it is out of scope here.

This matters for scope discipline. There is a persistent temptation to pull SAR
capability into this project because that is where the existing skill is. Resist it.
This project does not touch imagery.

### 1.4 The two-stage industry workflow, verified

The reason a triage layer exists as a distinct thing is that it is how the industry
actually works. This was verified rather than assumed.

Commercial SAR providers publicly describe in-house teams that monitor global weather
conditions 24/7/365 to anticipate potential flooding and **task satellites for imaging
accordingly**, initiating tasking when risk thresholds are met. The forecast data that
triggers the tasking is itself turned into alert data delivered to clients alongside
the imagery-derived product.

So the sequence is: cheap, fast, open-source monitoring → threshold crossed → decision
to task and analyse → expensive imagery-derived product. **This project builds the
first half.** Imagery-derived analysis is the second half.

One nuance worth carrying into the design: the trigger is a different kind of thing per
peril. Flood is anticipatory — you watch forecasts and task before the water arrives.
Earthquake is reactive — providers pre-image high-risk regions continuously, then produce
change detection once shaking occurs. Wildfire is ongoing — perimeter growth tracked
through the fire's life. Wind sits in between, with days of forecast cone followed by a
fixed landfall moment.

### 1.5 What success looks like

Not a validation score. Not a polished app. Success is:

- A working tool that ingests live data and produces a defensible ranked queue
- A written argument explaining the scoring design and where it diverges from published
  baselines, with the reasons
- Demonstrated handling of imperfect input data, specifically building footprints
- A clearly owned position on what should be prioritised and why, stated up front
  rather than deferred

---

## 2. What we are building

**A live monitoring and prioritisation tool for US natural catastrophe events, deployed
as a simple web application.**

In one paragraph: it polls three hazard feeds on a schedule, one per peril; writes what
it finds into a database holding a rolling one-to-two-week window; enriches each event
with an estimate of what is exposed underneath it; scores each event on two independent
axes, humanitarian and economic; ranks them; and presents the result as a map and a
table. Selecting a single event triggers an on-demand building footprint analysis for
that event's footprint only, which reports a *range* of building counts with the
disagreement between sources made explicit.

### 2.1 The three perils and their sources

| Peril | Source | Why this one |
|---|---|---|
| Earthquake | USGS | Best-in-class. One API gives event, PAGER alert, ShakeMap, and population exposed banded by shaking intensity |
| Wind (tropical cyclone) | NHC | The primary US advisory authority. First-hand track, wind radii and wind speed probabilities rather than a wrapper over them |
| Wildfire | NIFC WFIGS | Incident-level records with perimeters and operational attributes. Perimeters are what you prioritise on |

**Scope is the United States.** This is a deliberate simplification, taken so the
sources are consistent and the exposure layers are good. It is not a claim that the job
is US-only.

Two supporting layers sit alongside the three hazard feeds:

| Layer | Source | Role |
|---|---|---|
| Exposure — value | USACE/FEMA National Structure Inventory (NSI) | Structure and content replacement cost, occupancy type, population. Feeds the economic axis and (for wildfire/wind) the humanitarian axis. Section 5.6 |
| Exposure — buildings | VIDA merged footprints | The footprint comparison methodology. Section 7 |

And one source is **ingested and stored but deliberately not used yet**:

**GDACS is ingested into its own raw table and stored, but is not wired into scoring or
the front end.** The decision on whether to use it for anything is explicitly deferred
(open decision O14). Storing it is cheap and keeps the option open; wiring it in now
would commit to a design choice we have no reason to make yet. See section 5.4 for what
it does and does not give us, which is the reasoning behind the deferral.

### 2.2 Two levels of triage

Both are real and both should be built, because they are cheap once the data is in
place:

- **Between events.** Which of the live events matters most. This is the core
  operational question.
- **Within an event.** Which areas inside a single event footprint to look at first.
  This is where the building footprint drill-down lives.

### 2.3 What the user sees

A map with events plotted, and a ranked table alongside it. Click an event, get detail.
Interaction stays deliberately minimal — this is a view onto a queue, not an
interactive analysis environment. The existing wildfire dashboard is the reference
point for *level of polish*, not for feature count.

---

## 3. What this project is NOT

Read this section before writing any code. Every item here was considered and
deliberately excluded.

- **Not damage assessment.** This estimates what is *exposed*. It does not measure what
  was *damaged*. Damage requires before-and-after imagery and belongs to the SAR
  projects.
- **Not a SAR project.** No imagery is downloaded, processed, or analysed. No change
  detection. No coherence. Nothing from ASF, Copernicus Data Space, or any imagery
  archive.
- **Not global.** US only. This is settled.
- **Not flood.** Deliberately excluded. Flood is already covered by an existing
  portfolio project and adds a fourth data ecosystem for no gain.
- **Not a historical archive.** The database holds a rolling window of roughly one to
  two weeks. Older records drop out. The question the tool answers is "what is
  happening now", and permanent retention is a different product.
- **Not an SLA simulator.** Commercial providers' actual SLA durations, where their
  clock starts, and how they weight contract against severity are genuinely unknown and
  not publicly available. Do not model them. Do not invent numbers.
- **Not a shift-handover system.** Considered and dropped. Interesting, real, and out
  of scope.
- **Not a parametric trigger model.** Considered and dropped. Trigger locations and
  thresholds for live instruments are not publicly available in usable form.
- **Not an engineering showcase.** If a choice is between a more impressive
  implementation and a better-reasoned one, take the better-reasoned one.

---

## 4. Industry background — the reasoning the design rests on

This section exists so that a fresh context understands *why* the scoring is shaped the
way it is. It is also source material for the final write-up.

### 4.1 The existing public baselines are humanitarian-weighted

**GDACS** (Global Disaster Alert and Coordination System; renamed Global Disaster
*Awareness* and Coordination System in November 2025) is run by the European Commission
JRC with DG ECHO. It combines event parameters with population exposure, vulnerability
and **country-level coping capacity** to produce a continuous score and a colour band —
green, orange, red. The coping-capacity term is the key: GDACS is asking *will this
exceed national response capacity*, not *how big was it*.

Useful design patterns worth borrowing from GDACS:

- Red alerts forecast more than three days ahead are automatically downgraded to
  orange, an explicit documented decision about confidence versus lead time
- Events are flagged as changed when the score moves by +0.5 or the alert level
  increases — a ready-made definition of "what changed since I last looked"
- Alert volatility is accepted as normal; a cyclone can go red to green in 48 hours on
  a track change

**USGS PAGER** is earthquake-only but methodologically closer to a commercial view
because it estimates economic loss alongside fatalities. Its alert level is whichever
of two axes is worse:

- Fatalities: yellow at 1, orange at 100, red at 1,000
- Economic loss: yellow at $1M, orange at $100M, red at $1B

PAGER exists in that dual form for a specific reason: high fatality counts dominate
where local building practice produces high collapse rates, and economic loss dominates
elsewhere. The 2010 M8.8 Chile earthquake went **red on projected economic loss but
only orange on estimated fatalities**. That divergence is the whole point, and this
project generalises it.

PAGER also publishes a histogram of the likelihood that adjacent alert levels are
correct. If green and yellow are comparable in likelihood, the model cannot distinguish
them and says so. That is a directly reusable pattern for honest confidence
communication.

**Base rates matter.** Over 38 years PAGER issued roughly 17,792 green, 568 yellow, 52
orange and 49 red alerts. Orange-or-above is about one and a half events per year
globally. Swiss Re counted 190 natural catastrophe events worldwide in all of 2025.
Commercial SAR flood analysis runs at the order of tens of events a year globally.

**Design consequence: most of the time, nothing much is happening.** The tool must be
useful and legible when the queue is quiet. This is why the accumulating database is
the artefact rather than any single dramatic screenshot.

### 4.2 The commercial view diverges, and this is documented not theoretical

An insurance or reinsurance customer cares about insured exposure, which is close to
the inverse of coping capacity. This is not Sam's assertion — the industry publishes
its own decision rules.

**PCS (Property Claim Services, a Verisk unit)** designates catastrophes and assigns
serial numbers the market uses to track losses and trigger reinsurance and ILS
contracts. Designation is a three-test gate, all three required:

1. Expected insured loss above the regional threshold
2. The event is likely to impact **the majority of the insurance market**
3. The event is likely to produce **a significant number of claims**

Tests 2 and 3 are not severity. Breadth across the market matters as much as depth. A
single very large loss to one insurer does not qualify.

And the monetary threshold varies by region by a factor of eighty:

| Region | Threshold |
|---|---|
| United States | US$25M |
| Canada | C$25M |
| Mexico | MX$300M |
| Turkey | ₺10M |
| Japan | US$2bn |
| Rest of APAC | US$2.5bn |

The industry does not apply one global severity bar. It calibrates the bar to how much
insured value is there to lose. A humanitarian system would never do that.

**Aon Impact Forecasting's Automated Event Response** sends customised loss reports to
insurers automatically within 30 to 60 minutes of each new forecast cycle. Its peril
line-up is instructive: US Hurricane, Japan Typhoon, Australia Cyclone, European
Windstorm, European Hail, US Severe Convective Storm, Global Flood, US Wildfire,
Australia Bushfire. Some of these products are built on commercial Earth observation
data. The customer for an operational analyst's output is sometimes another firm's automated
pipeline with its own clock.

### 4.3 The divergence, quantified

Swiss Re sigma 1/2026, covering 2025:

- 190 events, USD 107bn insured, USD 220bn economic — a record 49% insured share
- Emerging economies: 80–90% of catastrophe losses uninsured
- Asia: 30% of global economic losses, about 5% of global insured losses

Worked examples, each usable in the write-up:

| Event | Humanitarian read | Commercial read |
|---|---|---|
| LA wildfires, Jan 2025 | Burned area below the California 10-year average | **USD 40bn insured**, costliest wildfire on record |
| Myanmar M7.7 | ~3,900 deaths, USD 11bn economic, minimal insurance | Near-irrelevant to insurers |
| Same event, Thailand | Far fewer casualties | **USD 1.5bn insured** — Bangkok's soft-sediment basin amplified shaking |
| Hurricane Melissa, Jamaica | Jamaica's costliest catastrophe on record, USD 8.8bn | Only a fraction insured |
| US severe convective storm | Not a GDACS hazard category at all | **Over USD 50bn insured for the third consecutive year** |

**The Myanmar/Thailand pair is the single strongest worked example.** One earthquake.
Humanitarian triage points at Myanmar, commercial triage points at Thailand, and
neither is wrong — they answer different questions.

### 4.4 Humanitarian and commercial are not usually in competition

Researched specifically, because it affects the scoring design.

Commercial SAR providers contribute data free of charge to the International Charter
"Space and Major Disasters" for humanitarian disasters. For Hurricane Melissa, rapid
flood and hurricane impact products were made **freely available** to government
agencies and NGOs through Esri's Disaster Response Program. MapAction used them to brief
arriving UN agencies; Team Rubicon used them to locate damaged infrastructure and clinic
sites with Jamaica's National Works Agency.

Melissa is the proof case: commercially thin, humanitarianly enormous, analysed anyway
and given away.

**So the humanitarian channel is real and structured, and for most events it is not
competing with the commercial one — it is the same analysis with different
distribution.** The customer base for commercial NatCat analytics is genuinely mixed:
insurers, government, emergency management, banking and utilities.

But analyst hours are still finite. If two events land in one shift and one is
insurance-heavy while the other is humanitarian-heavy, someone still chooses. How any
provider resolves that is unknown and should not be guessed at. See section 6 for how the scoring
handles this honestly.

---

## 5. Data sources — detailed

Everything in this section that is marked UNVERIFIED must be confirmed in Phase 0
before any design depends on it.

### 5.1 Earthquake — USGS

**Endpoint:** `https://earthquake.usgs.gov/fdsnws/event/1/query`

Core parameters: `format=geojson`, `starttime`, `endtime`, `minmagnitude`,
`minlatitude`/`maxlatitude`/`minlongitude`/`maxlongitude` for bounding box, or
`latitude`/`longitude`/`maxradiuskm` for radius. Also `orderby`, `limit`, and filters on
depth, event type, alert and review status. A `count` method exists with the same
parameters.

USGS recommend polling the **pre-built real-time GeoJSON summary feeds** rather than
`query` for routine monitoring, for performance and availability. Use those for the
scheduled poll and `query` for backfill or specific lookups.

**Fields available in the summary feed** (per feature, under `properties`):

- `mag`, `place`, `time`, `updated`, `tz`, `felt`, `cdi`, `mmi`, `type`, `title`
- `sig` — a USGS significance score computed from magnitude, felt reports and impact.
  A cheap pre-existing composite worth comparing your own score against.
- `tsunami` — **a flag, not a forecast.** Set when the event meets regional tsunami
  warning centre notification criteria, typically M≥7.0, shallow and offshore. Do not
  treat as a tsunami severity signal.
- `alert` — the PAGER alert colour. **This is null for most events.** PAGER only runs
  for events large enough to warrant it, roughly M5.5+ globally and lower in populated
  areas. The ingest must handle null gracefully and not treat absence as green.

**The two-tier fetch problem.** The summary feed carries only the PAGER colour. The
fatality and economic loss distributions, and population exposed by Modified Mercalli
Intensity band, live inside the `losspager` product, reachable only via a single-event
query at `?eventid={id}&format=geojson`, which returns a single Feature (not a
FeatureCollection) with a `properties.products` object containing `origin`, `shakemap`,
`dyfi`, `losspager`, `moment-tensor`, `finite-fault` and others.

**Design consequence: cheap screening on the summary feed, expensive enrichment per
event.** Only fetch `losspager` for events that clear a screening threshold. Budget one
extra HTTP call per qualifying event. This same pattern recurs with building
footprints — it is the shape of the whole system.

`properties.ids` carries non-authoritative aliases as a comma-padded string; any of them
resolves via the same endpoint.

### 5.2 Wind — NHC

**Feed — corrected 2026-08-23 (Phase 0):** `https://www.nhc.noaa.gov/gis/rss.php` is
actually a documentation/landing page, not a feed — fetching it returns HTML, not RSS.
The real per-basin feeds live at `/gis-at.xml`, `/gis-ep.xml` etc., and real per-storm
product filenames follow a different pattern than originally assumed —
`AL112017_020adv_CONE.kmz` style (basin, storm number, year, advisory number, product
code), not `gis-{product}-{yyyymmddhhmm}`. That GUID-style pattern turns out to be
specific to the basin-wide wind-speed-probability product family
(`2026082306_wsp64knt120hr_5km.kmz` style), not a general one.

**Better polling target, found during verification and not in the original plan:**
`https://www.nhc.noaa.gov/CurrentStorms.json`. One JSON call returns every active storm
across all basins (Atlantic, East Pacific, Central Pacific) with direct URLs to every
GIS product per storm per advisory — track, cone, wind radii, wind speed probabilities
at 34/50/64kt, storm surge (null when not in effect, confirming the note below), best
track. Tested live: as of 2026-08-23 both Atlantic and East Pacific are quiet, but two
Central Pacific storms are active — confirming the JSON reflects real current state
across basins the two named RSS feeds don't cover on their own.

**Decision (2026-08-23): ingest both, don't replace one with the other yet.** Same
demote-don't-delete logic already applied to GDACS (section 5.4, D8) — poll both the
per-basin RSS feeds and `CurrentStorms.json` at Phase 2, store what each actually
returns, and decide afterward whether one is redundant, whether they cover different
edge cases, or whether one turns out more reliable in practice. Doesn't change decision
D6, only the implementation. Full detail in `DECISIONS.md` (Phase 0 verification findings).

**Products relevant here:**

- Track forecast cone and forecast points, per advisory
- **Wind radii** — the extent of 34, 50 and 64 knot winds. The natural exposure
  footprint for wind, since it bounds where damaging winds actually reach.
- **Wind speed probabilities** — cumulative probability of sustained winds reaching 34,
  50 or 64 kt, at 0.5 degree and 0.1 degree resolution, in cumulative 12-hour steps out
  to 120 hours. Shapefile and KMZ.
- Probabilistic storm surge, available **only while US watches or warnings are in
  effect**

Updated every 6 hours with each advisory package. Note the forecast cycle begins 3 hours
before the advisory is issued, so the centre position on a graphic is 3 hours older than
the advisory timestamp.

The 34/50/64 kt thresholds map directly onto insurance thinking (64 kt is hurricane
force) and give a natural severity gradient without inventing one.

**Seasonality:** the Atlantic season runs roughly June to November. Outside it this feed
will be quiet. Plan for the tool to be honest about that rather than looking broken.

### 5.3 Wildfire — NIFC WFIGS

NIFC publish the Wildland Fire Interagency Geospatial Services (WFIGS) datasets through
ArcGIS REST services on the NIFC Open Data portal. Two layers matter:

- **Incident locations** — point per incident, with attributes typically including
  incident name, discovery date, cause, acres, containment percent, and incident
  complexity
- **Perimeters** — polygon per incident, updated as the fire grows

**UNVERIFIED: the exact service URLs, layer ids, field names and update cadence.**
Confirm in Phase 0. The existing wildfire dashboard project already consumes WFIGS and
its code should be checked first rather than rediscovering the endpoints.

**Why NIFC and not FIRMS.** FIRMS gives thermal hotspot detections — points where
something was burning at satellite overpass. That tells you an ignition happened. It
does not tell you whether the fire matters, how big it has become, or what it is
threatening. Perimeters and incident attributes are what prioritisation runs on.
Hotspots may still be useful as a secondary signal for very new fires that have no
perimeter yet, but they are not the primary source.

### 5.4 GDACS — ingested and stored, not yet used

**Build the ingest. Store the records. Do not wire it into scoring or the UI.**

The reasoning matters, so it is set out fully. GDACS is the obvious-looking multi-hazard
spine and was the recommended architecture for two planning rounds before being demoted.
Anyone picking this project up will have the same instinct, so here is what it does and
does not give us.

**Per peril, against what we already have:**

*Earthquake — nothing.* GDACS publishes no structured exposure figures for earthquake at
all. IFRC's own ingest documentation states that for earthquake, drought, tsunami and
volcano the alert score and population exposure appear only in the free-text event
description, and that parsing it was judged too unreliable to specify a mapping for.
USGS gives all of this structured. GDACS is strictly worse here.

*Wind — genuinely something.* GDACS wraps the advisory agencies' cyclone data and adds
its own computed population figures: people inside the 39 kt wind field (`pop39`),
people inside the 74 kt field (`pop74`), and people in the storm surge zone
(`popstormsurge`), per advisory point along the track. NHC gives the wind radii but not
a population count inside them.

**But taking it would break cross-peril comparability.** We compute population exposure
ourselves for earthquake and wildfire. Using GDACS's number for wind only would mean the
wind score rests on different underlying population data and a different method from the
other two, making the ranking between perils meaningless. Computing it ourselves three
times the same way is worse data and better analysis.

*Wildfire — nothing usable.* Threshold too high; see below.

**As a comparison baseline — weak.** PAGER already provides a published alert to compare
against for earthquake, with actual fatality and loss numbers rather than a colour. For
wind and wildfire, the GDACS alert is a judgement about whether an event exceeds
*national response capacity*. Comparing a US event against that is close to
meaningless — for the United States the answer is almost always no.

**So why store it at all?** Because the ingest is cheap, the records are small, and it
preserves the option. If the scoring work later wants a published humanitarian cross-check,
or a validation check against our own computed population figures, the data will already
be there rather than needing a retrofit. This is a deferral, not an endorsement.

**Two findings from the demotion that stay relevant regardless:**

**Its wildfire severity metric is hectares burned, and that is decoupled from
structure value — verified directly, and the finding is sharper than first assumed.**

GDACS does have a two-tier wildfire filter: an automated initial filter at 5,000 ha,
and a homepage-display filter at 10,000 ha AND population within 5 km over 10,000
(confirmed against `gdacs.org/Knowledge/models_WF.aspx` and the MHEWS guide, Phase 0,
2026-08-23). The Palisades Fire burned roughly 23,000 acres (about 9,300 ha) and Eaton
roughly 14,000 acres (about 5,700 ha) — both clear the 5,000 ha initial filter, neither
clears the 10,000 ha homepage filter.

**PHASE 0 FINDING (2026-08-23, corrects the original hypothesis below):** the original
plan for this section assumed GDACS would have missed the LA wildfires entirely on
hectare count alone. **That is wrong.** Querying GDACS's SEARCH endpoint directly for
2025-01-01 to 2025-02-15 returns two Orange-level US wildfire events dated 2025-01-07
and 2025-01-08 — the actual Palisades/Eaton ignition dates, with recorded severity of
8,219 ha and 4,677 ha. GDACS's own documentation explains why: alongside the two
automated filters there is an explicit manual-override path — "When a smaller wildfire
could potentially cause humanitarian impacts (e.g. contiguous to urban areas), this
event is manually inserted into the GDACS system upon expert judgement." Both LA fires
were evidently inserted this way.

**The real, verified finding is better than the one originally hypothesised.** GDACS
did not miss this event — it tracked it, at Orange, and (per the same SEARCH query)
never escalated it to Red at any point across its recorded episodes. An event that
became the costliest wildfire in US insurance history (~USD 40bn insured) topped out
at the same alert colour GDACS would give a moderate regional wildfire. The failure
isn't a missed event — it's that **GDACS's wildfire severity metric (burned hectares)
is structurally decoupled from structure value.** A fire that burns 8,000 ha of
chaparral and one that burns 8,000 ha of dense suburban housing score identically under
this metric, despite radically different commercial and humanitarian consequences.
That is the same underlying argument the plan wanted to make about metric mismatch —
just now a verified fact rather than an unverified hypothesis. Full verification detail
in `DECISIONS.md` (Phase 0 verification findings).

**Endpoint for the ingest:**
`https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH` with `eventlist`
(semicolon-separated type codes EQ, TC, WF, FL, VO, DR, TS), `fromdate`, `todate`,
`alertlevel` (semicolon-separated). Maximum 100 records per call, ordered by `todate`
descending, with paging by page size and page number. No key required. Attribution
required: "Global Disaster Alert and Coordination System, GDACS". Source data licence is
MIT.

**Known GDACS traps, if used:**

- `geteventdata` silently ignores the `episodeid` parameter and always returns the
  current episode. Use the per-episode URL published in `properties.episodes[].details`.
- The cyclone timeline is cumulative — every episode re-returns all earlier advisory
  entries. Key on the entry's own `id`, not the episode, or you create a duplicate per
  update.
- There is a `pop` field in the cyclone timeline that looks like a headline population
  figure and is not. Its definition is unpublished and it behaves inconsistently — in
  one documented advisory it reads zero while `pop39` counts 75 million. **Do not use
  it.** Use `pop39` and `pop74`.
- Detailed geometry comes from a separate `getgeometry` call returning a FeatureCollection
  with several nested layers; the affected-area polygon is the feature with
  `properties.Class = "Poly_Affected"`.
- **Verified 2026-08-23 (Phase 0):** the SEARCH endpoint responds normally to a real HTTP
  client with default headers. The HTTP 400 seen during research was a research-tool
  artefact, not an outage.

### 5.5 Exposure layers

**Population.** Options are WorldPop, LandScan (Global and HD), GHS-POP and GPW. None
are census data — all are modelled surfaces redistributing coarser official statistics
onto a grid using proxies like night-lights, land cover and building density.

The operationally important distinction: **LandScan models *ambient* population** —
where people actually are through an average day, accounting for work and travel.
**WorldPop primarily models *residential* population** — where people sleep. A wildfire
hitting a business district at 2pm has a completely different real exposure than the
same area at 2am. Which product you reach for should depend on time of day relative to
the event, not on which is "most accurate".

GHS-POP is what GDACS itself uses, via the Copernicus EMS Exposure Mapping component,
which is an argument for it on comparability grounds.

Known failure modes to carry into the QC:

- Accuracy is regional, not universal. Different studies crown different winners —
  WorldPop best in a China comparison, LandScan best across mainland Southeast Asia,
  mixed results across Myanmar, Laos and Cambodia in the same study.
- A Sweden validation study found both WorldPop and GHS-POP **consistently
  overestimated** population exposed to flooding. Overestimation bias is as real as
  under-counting.
- WorldPop's detailed modelling is only re-run for census-anchored years (2010, 2015,
  2020); every other year is linearly interpolated, which its own documentation
  acknowledges may produce unrealistic results at grid-cell level.
- LandScan's own 2025 methodology paper warns that traditional population modelling
  often overlooks inherent uncertainties, creating a false sense of certainty that can
  lead to flawed decisions. That is the dataset's creators warning against trusting a
  precise-looking number.

**Buildings.** See section 7 — this is a methodology in its own right, not just a layer.

**Economic proxies, globally.** VIIRS night-lights and gridded GDP are the available
open options. Neither is insured value, and both really only say "there is economic
activity here". There is **no open gridded insurance penetration product**; Swiss Re
sigma publishes regional and national figures annually in PDF only.

For the US specifically there is something much better — see 5.6.

### 5.6 Economic exposure — National Structure Inventory (NSI)

**What it is.** A national point-based structure inventory built and maintained by the
US Army Corps of Engineers, with FEMA involvement, and integrated into FEMA's HAZUS
database. Each point represents one structure. It exists specifically so that agencies
can assess and analyse the consequences of natural hazards — flood has been the primary
use, but the documentation states explicitly that sufficient data exists per structure to
evaluate other hazard types.

It is included because the economic axis otherwise had no real data behind it. It is
**not** a replacement for the population or building layers, both of which are already
well served. It fills one specific hole.

**Attributes that matter here:**

- **Depreciated replacement cost of the structure, and separately of its contents.**
  Content values are derived from occupancy-type ratios.
- Occupancy type, aggregating to residential, commercial, industrial and public
- Number of storeys, foundation type and height, exterior construction material
- **Population day and night, split over and under 65**

**Access.** An API supporting query by polygon, bounding box or FIPS code, returning
GeoJSON. Bulk GeoPackage downloads per state are also available. The documentation
advises that where the same inventory is used repeatedly it is better to download and
store locally than to call the API repeatedly — relevant if a particular region is
queried often. The API root has moved over the tool's life, so resolve it from current
documentation rather than hardcoding a remembered URL.

Coverage is all 50 states and DC. Not all US territories.

**Structures are points, not polygons**, so intersecting with a hazard footprint is
point-in-polygon rather than polygon overlay. Cheaper and simpler than the footprint
work.

**What it usefully solves beyond the economic axis — decided 2026-08-23, O6 resolved:**

NSI's own population figures feed the humanitarian axis for wildfire and wind. **The
day/night switch itself is dropped** — the precision it implies (picking a figure based
on event time-of-day) isn't real precision, given these are modelled annual estimates,
not something genuinely accurate to time-of-day. Use a single population figure; state
the ambient-vs-residential distinction as a limitation in the write-up rather than
building a time-of-day branch around it.

Verified empirically (Phase 0, 2026-08-23) that NSI avoids the specific failure mode
that affected `WildfireDashboard`'s Census-tract population data: because NSI is
point-based (one row per structure) rather than polygon-averaged, population doesn't
get smeared flatly across large, mostly-empty rural areas. Checked directly against a
real sparse rural bounding box (Arthur County, Nebraska — one of the least populated
counties in the US): agricultural/farm structures scattered across empty land correctly
show zero population, while population clusters exactly at the actual town's houses,
school, and church. See `DECISIONS.md` (Phase 0 verification findings) for the sample data.

For **earthquake**, O6 doesn't apply at all: USGS's own PAGER population-exposure
numbers (`exposures.json`, confirmed live in Phase 0) are already computed from
LandScan internally, so population-by-MMI-band comes for free from USGS and doesn't
need independently computing.

The over-65 counts still give the humanitarian axis a vulnerability dimension that is
defensible rather than invented. Coping-capacity indices do not discriminate much within
the US; age structure does.

**Limitations that must be stated, not buried:**

- **Replacement cost is not insured value.** It is what rebuilding would cost,
  depreciated. Far closer than night-lights, but the gap to insured loss is real —
  coverage limits, deductibles, whether the peril is covered at all. This remains the
  project's largest stated limitation on the economic side.
- **Vintage.** The 2019 release indexed population to 2017 levels and prices to 2018. A
  2022 base layer exists, so the current vintage must be checked in Phase 0. This is the
  same "vintage is a silent limitation" pattern that applies to every other layer here,
  and it applies to the flagship input of the economic score.
- **The NSI team's own caution:** separating land value from structure value is
  extremely difficult, and they say so. Publisher self-criticism worth citing.
- **UNVERIFIED — licensing.** NSI draws on CoreLogic data with a restrictive use
  agreement for some datasets, while the base layer appears publicly available. Confirm
  in Phase 0 before the plan depends on it.
- It is a **modelled inventory**, generated from analysis of building footprints, parcel
  datasets and Census data. It is not a survey. Treat it with the same scepticism as
  every other modelled layer in this project.

---

## 6. Scoring design

### 6.1 Terminology — get this right

**Exposure** is the presence of people, assets or infrastructure in a hazard-prone area.
**Impact** is the effect the hazard has on them. UNDRR keep these formally separate and
so must this project.

This project measures **exposure**. It counts what was underneath the footprint. It does
not measure impact, and it does not measure damage.

Correct: "180,000 people exposed", "4,200 buildings within the perimeter".
Incorrect: "180,000 people affected", "4,200 buildings damaged".

GDACS observe the same line — IFRC's mapping documentation types all GDACS population
figures as `potentially_affected` with `estimate_type: modelled`, noting explicitly that
they count persons inside a hazard footprint, not persons the hazard harmed.

This is not pedantry. It is the boundary between this project and the SAR projects, and
getting it wrong in a write-up is the kind of overclaim a careful reader will find.

### 6.2 Two axes, not one blend

**Decision: score humanitarian and economic exposure separately, keep both visible, and
derive an overall score as the worse of the two.**

The rationale is threefold.

*It is honest.* Weighting a life against a dollar requires a number nobody has, and
hiding that number inside a single blended score would be exactly the kind of false
precision this project is supposed to be arguing against.

*It has direct precedent.* This is how PAGER works — two independent axes, thresholds on
each, headline alert set by whichever is worse. The 2010 Chile earthquake going red on
economic loss and orange on fatalities is the canonical illustration.

*It reflects the actual customer mix.* Commercial NatCat analytics serves insurers,
governments, emergency management, banking and utilities. A single commercially-weighted
score would misrepresent who the output is for. Section 4.4 documents that humanitarian
events are analysed anyway and distributed free through the Charter and Esri's Disaster
Response Program.

The max rule also sidesteps the unanswerable weighting question entirely: an event that
is severe on either axis rises to the top, and an event moderate on both does not.

**The user can sort by humanitarian score, economic score, or overall.** That is the
feature that makes the honesty visible rather than just stated.

### 6.3 What feeds each axis

Indicative, not settled — the specific formulation is an open decision (O4, O5).

**Humanitarian axis:** population exposed within the hazard footprint, weighted by
hazard intensity where the source provides it (MMI bands for earthquake, wind speed
bands for cyclone). **O6 resolved (2026-08-23):** earthquake population exposure comes
directly from USGS PAGER (already LandScan-based internally, no separate computation
needed); wildfire and wind use NSI's own population figures, as a single count — no
day/night switching (see section 5.6). The over-65 split gives a vulnerability
weighting. Note that coping-capacity and vulnerability indices are less discriminating
within the US than globally, a direct consequence of the US-only scope.

**Economic axis:** structure and content replacement cost summed across NSI points
within the hazard footprint, with occupancy mix available as a secondary signal —
commercial and industrial exposure behaves differently from residential. State
explicitly that this is *replacement cost*, not insured value, and that the gap between
them is the project's largest stated limitation on this axis.

**Confidence.** Every score carries a confidence indication. Where the underlying data
is thin — no PAGER product, no perimeter yet, single-source building footprints — the
score says so rather than presenting a bare number. PAGER's likelihood histogram is the
pattern to borrow.

### 6.4 The comparison

For every event that GDACS or PAGER also scored, record their published alert alongside
the project's own. The divergences are the analytical output. Where the project ranks
something differently, the write-up explains why.

---

## 7. Building footprint methodology

This is the part of the project that closes a specific, named gap. It deserves care.

### 7.1 The gap it closes

A common operational situation: *a client reports fewer buildings than you identified —
for example rock formations misidentified as buildings — how do you handle that?* Typical
validation work checks outputs against ground truth after the fact, but assumes the
inputs are correct. This is the input-integrity problem, and it is different.

The diagnostic process, which should inform the implementation:

1. Pull the detected features for that specific area and overlay on real imagery —
   visually confirm which are real rather than guessing from the count
2. Check whether the extras are clustered or scattered. Clustered around one feature —
   a rock formation, a dock, a shadow — points to a single bad detection event.
   Scattered points to something systemic.
3. Check provenance on the false-positive features specifically. OSM keeps full edit
   history per object, so you can see whether a polygon came from a manual trace or a
   bulk import, and when.
4. Cross-reference against a second independent building source **for that area only** —
   using a second source to catch what the first got wrong, not to replace it wholesale
5. Fix depends on findings: filter by confidence score where the source provides one;
   add a geometric sanity check (real buildings cluster around regular rectangular
   forms, natural features often do not); or flag as a known regional limitation and
   adjust expectations

Relevant nuance: the OSM community has explicitly rejected bulk-importing AI-derived
building data on geometric quality and false positive grounds, but reviewed piecemeal
imports of exactly that ML data do happen regionally after community sign-off, with
documented examples in Nottinghamshire, Australia and several US counties. So "it's OSM
data" and "it's an ML false-positive problem" can be the same answer rather than
competing ones.

Industry confirmation that this is a real known risk, not an edge case: Esri's own
damage-assessment model documentation, developed for the 2023 Lahaina wildfires,
explicitly flags building footprint accuracy as a known dependency, noting that accuracy
varies with the method used to create the footprint layer and that footprints should be
accurate to the incident imagery being used.

### 7.2 The data

**Primary: the VIDA merged dataset** — Google Open Buildings V3, Microsoft
GlobalMLFootprints and OpenStreetMap, already conflated into roughly 2.7 billion
footprints, **each one labelled with its source**. Published at
`source.coop/vida/google-microsoft-osm-open-buildings`, divided into 200 partitions,
available as GeoParquet, FlatGeobuf and PMTiles.

Using this means not building the conflation yourself, which would be a project in its
own right, while still getting the source labels — which are the entire point.

An alternative worth noting: **OpenBuildingMap** conflates the same three sources with
quality-based precedence and adds occupancy type, height, storeys and floorspace using
the GEM Building Taxonomy, explicitly aimed at disaster risk work. Richer attributes,
but the precedence logic hides the disagreement this project wants to surface. Recorded
as open decision O8.

**Confidence scores — verified 2026-08-23, with an important scope limitation.** Google
publish a per-footprint confidence score and explicitly recommend filtering below their
estimated 90% precision threshold. Their own documentation names the errors to expect:
false detections and inaccurate shapes. The `confidence` field does survive into the
VIDA merge — confirmed directly by reading a live FlatGeobuf file's schema
(`bf_source`, `confidence`, `area_in_meters`, `s2_id`, `geohash` all present).

**But it is not usable for this project.** Querying the actual USA FlatGeobuf file over
a real bounding box (part of the Eaton fire area, Altadena) returned 28,136 buildings
sourced entirely from `microsoft` and `osm` — zero `google`-sourced rows. This isn't a
sampling gap: Google Open Buildings V3 deliberately excludes the United States and
Europe from its coverage, by design — its stated scope is Africa, South Asia,
Southeast Asia, and Latin America/Caribbean, on the grounds that the US and Europe
already have strong Microsoft/OSM coverage. For this project's US-only scope, there is
no Google-sourced data to filter, so the confidence-filter variant described below in
section 7.4 is a non-event, not a fourth comparison. Full detail in
`DECISIONS.md` (Phase 0 verification findings).

Regional note consistent with everything else in this project: one comparison concluded
OSM is the best base layer for all continents except South America and Africa, where
Google Open Buildings wins. Global reputation does not predict regional reliability —
and, per the finding above, it doesn't even predict *coverage* in every region.

### 7.3 When it runs

**On demand, per event, never in the ingest.**

Nobody queries 2.7 billion footprints on a timer, and more importantly nobody needs to.
This mirrors the USGS PAGER pattern exactly: cheap screening on everything, expensive
enrichment only where it has been earned. The decision to spend the effort is itself
part of the triage judgment, and building it that way demonstrates that.

Trigger: user opens an event. The system then fetches footprints for that event's
bounding box only, runs the analysis below, and caches the result for the life of that
event in the rolling window.

### 7.4 The method — four counts and a classification

**Produce four counts for the same area and report all four.**

| Count | Definition | Meaning |
|---|---|---|
| A | OSM only | Human-mapped, conservative baseline |
| B | Union of all sources | Maximum plausible count |
| C | Agreement-filtered — seen by two or more sources | Confident count |
| D | NSI structure points within the footprint | Independent modelled inventory, built from footprints, parcels and Census |

**The spread between these is the deliverable, not any single number.** If OSM says 400,
the union says 900, agreement says 520 and NSI says 480, that tells a client something
real: roughly 500 buildings you are confident about and 400 that only one automated
model believes in.

Count D is worth having precisely because NSI is derived differently — it draws on
parcel and Census data, not only imagery-derived footprints, so it fails differently.
Where NSI and the footprint agreement count are close, confidence is high. Where they
diverge sharply, something is wrong with one of them and that is worth saying rather
than averaging away. Note that NSI counts *structures* while the footprint sources count
*detected building outlines* — they are not measuring quite the same thing, which is
itself part of the explanation when they disagree.

Report a range with an explanation of what drives it. This is the same discipline as the
`no_data` and `geometry_limited` exclusions from the denominator in the existing
wildfire project — do not pretend uncertain data is certain — applied to inputs rather
than outputs.

**Then classify the disagreements.** Overlap the sources pairwise and sort every
footprint into one of four relationships:

| Relationship | Meaning | Is it an error? |
|---|---|---|
| 1:1 | Both sources agree there is one building here | No |
| 1:0 | Only one source sees anything at all | **False-detection candidate** |
| 1:n | One source's building overlaps several in the other | No — a splitting disagreement |
| m:1 | Several footprints correspond to one in the other | No — a merging disagreement |

This distinction is the core of the input-integrity problem. "Fewer buildings than you
found" can mean a rock formation got detected, which is a 1:0 case, or it can mean one
warehouse got split into three, which is a 1:n case. **They need completely different
responses, and they are geometrically distinguishable.** The splitting cases do not
affect total area at all, only counts — which matters enormously if you are counting
buildings and not at all if you are measuring footprint area.

**Where confidence scores are available**, apply the Google 90% precision filter as a
fourth variant and report how many footprints it removes. **Verified 2026-08-23: not
available at this project's US-only scope** — Google Open Buildings has zero coverage
in the United States (section 7.2), so there are no Google-sourced confidence scores to
filter on. The counts A/B/C/D in the table above stand as the actual deliverable; the
confidence filter drops out rather than becoming a fifth count.

**Sam explicitly wants multiple methods compared with outcomes for each.** That is the
design above. Do not collapse it to a single number to make the UI tidier.

### 7.5 What to report per event

- The four counts and the range
- How far NSI sits from the footprint agreement count, and in which direction
- Count of 1:0 cases, flagged as false-detection candidates
- Count of splitting/merging disagreements, flagged as counting artefacts not errors
- Total footprint area, which is robust to the splitting problem where counts are not
- A plain-language confidence statement

---

## 8. Architecture

### 8.1 Database

**One database. Separate tables.**

- **One raw table per source**, each shaped to that source's own structure. No forcing
  USGS fields into an NHC shape. When something looks wrong you can see what the source
  actually said rather than what your translation made of it, which matters for a
  project partly about data trust.
- **GDACS gets a raw table and nothing else.** It is ingested and stored but does not
  write into the unified events table, does not feed scoring, and does not appear in the
  UI. If O14 later resolves in favour of using it, the data will already be there.
- **One unified `events` table** that every ingest writes a normalised row into: event
  id, source, peril, name, location, footprint geometry, event time, last updated,
  common severity fields, the three scores, and a confidence indication.
- **One `building_analysis` table** caching the on-demand footprint results per event.

The compatibility problem gets solved once, deliberately, in each source's ingest code.
That is the right place for it — the translation is genuinely different per peril and
making it generic would be worse. The app reads only the unified table.

**Rolling window.** Roughly one to two weeks. Records older than the window are removed.
Events are **overwritten in place** as new data arrives rather than versioned — the tool
answers "what is happening now", and change history is a different product.

**Destructive operation warning.** Any routine that deletes rows outside the window, or
truncates and reloads, must be flagged to Sam in detail before first use and must be
tested against a copy. This is exactly the class of operation his working preferences
call out.

**O10 resolved (2026-08-23): plain Postgres, geometries as WKT/GeoJSON, shapely for all
intersection/overlay math.** Matches `WildfireDashboard`'s pattern. Justified
specifically because this project's *local* database only ever holds a small rolling
window of event-level footprints (dozens to low hundreds of rows) — the heavy geometry
work (VIDA footprints, NSI points) runs against externally bbox-filtered API results,
computed transiently in Python, with only summary results cached locally. PostGIS's
spatial indexing has little to bite on at that scale. Revisit only if a real query need
emerges that plain Postgres can't serve reasonably.

### 8.2 Ingest

One scheduled job per source. Each one:

1. Polls its feed
2. Writes raw records to its own table
3. Normalises into the unified events table, upserting on the source's event id
4. Triggers enrichment for events that clear a screening threshold
5. Recomputes scores
6. Prunes records outside the rolling window

Poll frequency should follow each source's own update cadence — no point polling NHC
more often than 6-hourly, since that is when advisories issue. Actual cadences are open
decision O2.

**Every ingest must handle its feed being down, slow, or returning malformed records
without taking the tool with it.** Outages are normal. Log them; the job description
mentions documenting errors and outages for a reason.

### 8.3 Application

React front end, map plus ranked table, following the existing wildfire dashboard for
level of polish. Stack decision is open (O11) but reusing what already exists is the
default unless there is a reason not to.

Views:

- **Queue** — ranked table, sortable by humanitarian, economic or overall score,
  filterable by peril
- **Map** — events plotted with footprints where available
- **Event detail** — everything known about one event, the score breakdown, the GDACS or
  PAGER comparison where one exists, and the button that triggers the building analysis

Keep interaction minimal. This is a view onto a queue.

---

## 9. Phase plan

### Phase 0 — Verification, before any build

No code beyond throwaway scripts. Confirm every UNVERIFIED item:

1. USGS summary feeds and single-event product fetch — confirm structure and that
   `alert` and `losspager` behave as described
2. NHC RSS feed — confirm GUID patterns, product availability, and what parses cleanly
3. NIFC WFIGS — find the actual service endpoints and field names. **Check the existing
   wildfire dashboard project first.**
4. VIDA dataset — confirm access, format, partitioning, and whether Google confidence
   scores survive the merge
5. GDACS SEARCH endpoint — confirm it responds to a real HTTP client
6. **The GDACS 10,000 ha wildfire threshold** — verify against current documentation.
   This claim carries real weight in the write-up and must not go in unverified.
7. **NSI** — resolve the current API root from documentation rather than assuming;
   confirm the bounding-box query, the current data vintage, and the licensing position
   on the base layer
8. Population layer availability and licence for whichever product O6 selects

Output: a short written verification note recording what is live, what is not, and what
changed from the assumptions in this plan.

### Phase 1 — Single-peril spine

Build the whole vertical slice for **earthquake only**: ingest, raw table, unified table,
a first scoring pass, and a minimal display. Earthquake first because USGS is the
best-behaved source and PAGER gives an immediate comparison baseline.

Output: working end-to-end pipeline for one peril.

### Phase 2 — Remaining perils

Add NHC and NIFC ingests into the same unified table. This is where the normalisation
design gets tested properly.

Also add the GDACS ingest here, writing to its raw table only. It is small, it is
isolated, and doing it alongside the others is cheaper than retrofitting later.

### Phase 3 — Scoring

Build the two axes and the overall. This is where NSI enrichment gets wired in — the
point-in-polygon intersection against each event footprint, feeding replacement cost to
the economic axis and (for wildfire/wind) population to the humanitarian axis.

Compare against PAGER where available. Document divergences with reasons.

### Phase 4 — Building footprint drill-down

The four counts, the classification, the confidence filter, the caching.

### Phase 5 — Application

Map, table, event detail. Deploy.

### Phase 6 — Write-up

The reasoning from this document plus whatever Phases 0 to 5 actually found. Failures
reported, not omitted.

---

## 10. Decisions already made

| # | Decision | Reasoning |
|---|---|---|
| D1 | This project runs first, before the SAR projects, which continue separately afterwards | It demonstrates triage judgment; the SAR projects demonstrate technique. They do not need to be linked into one story |
| D2 | Live data, not historical replay | The purpose is a current operational picture. The accumulating database is the artefact, which solves the "nothing is happening today" problem without needing replay |
| D3 | US scope only | Keeps sources consistent and exposure layers good. Simplification, not a claim that real operations are US-only |
| D4 | Three perils: earthquake, wind, wildfire. No flood | Flood is already covered by an existing portfolio project and adds a fourth data ecosystem for no gain |
| D5 | USGS for earthquake | Best-in-class; gives event, PAGER alert, ShakeMap and MMI-banded exposure from one API |
| D6 | NHC for wind, not GDACS | The primary US advisory authority; first-hand track, wind radii and probabilities rather than a wrapper over the same advisories |
| D7 | NIFC for wildfire, not FIRMS | Hotspots indicate ignition, not significance. Perimeters and incident attributes are what prioritisation runs on |
| D8 | GDACS ingested and stored, but not wired into scoring or the UI; use deferred to O14 | It supplies nothing the other sources do not, except wind population figures that would break cross-peril comparability if used alone. But the ingest is cheap and storing it preserves the option without committing to a design choice we have no reason to make yet |
| D16 | NSI added as an additional source for the economic axis | It is the only open US layer giving an actual value figure per structure. Not a replacement for the population or building layers, which are already well served — it fills one specific hole |
| D17 | NSI structure count becomes a fourth comparison in the building footprint analysis | It is derived from parcel and Census data as well as footprints, so it fails differently from the imagery-derived sources. An independent view is worth more than a fourth similar one |
| D9 | One database, separate raw tables per source plus one unified events table | Solves compatibility once per source, deliberately, in the right place; preserves what the source actually said |
| D10 | Rolling one-to-two-week window, overwrite in place, no change history | The tool answers "what is happening now" |
| D11 | Two scoring axes — humanitarian and economic — with overall as the worse of the two | Honest about an unknowable weighting; direct PAGER precedent; reflects the genuinely mixed customer base of commercial NatCat analytics |
| D12 | Building footprint analysis on demand per event, never in the ingest | Scale makes global infeasible and operational work does not run that way either. Mirrors PAGER's cheap-screen/expensive-enrich pattern |
| D13 | Report four building counts and a range, not a single number | The spread is the finding. Same discipline as the wildfire project's exclusions, applied to inputs |
| D14 | Deployed web app, minimal interaction | Portfolio legibility; others can view it without setup |
| D15 | Exposure, never damage or impact | Formal UNDRR distinction; also the boundary against the SAR projects |

---

## 11. What nearly went wrong — do not repeat these

Every item here was actually proposed or drifted into during planning, and rejected.
Read this before suggesting anything.

**11.1 — Research rabbit-holing.** Planning went very deep into insurance industry
mechanics: PCS resurvey cadences, parametric trigger taxonomies, industry loss warranty
structures, FNOI versus FNOL, follow-the-sun shift handover. All real, almost all
irrelevant to a first project. The useful residue is in section 4 and it is
deliberately short. **Do not expand section 4. If a fascinating industry detail surfaces
during the build, note it and move on.**

**11.2 — Building features because reference material mentioned them.** Every feature
must trace back to the triage question in section 2, not to what some example workflow
happened to include. Reference material is inspiration, not a specification.

**11.3 — GDACS as the data spine.** This was the recommended architecture for two
rounds, on the reasonable grounds that one API across three perils minimises complexity.
It would have failed. GDACS publishes no structured earthquake exposure at all, and its
wildfire threshold is high enough that the costliest wildfire event in history probably
would not have appeared. **The lesson generalises: check what a source actually returns
per event type before designing around it.** An API that covers many hazards may cover
them very unevenly.

**11.4 — FIRMS for wildfire.** Proposed as the global option. Hotspots tell you
something ignited, not whether it matters. Sam caught this. Perimeters are what
prioritisation runs on.

**11.5 — ESWD for severe convective storm.** Listed in early research as a wind data
source. Its User's Agreement **prohibits commercial use** and requires a signed
agreement returned to ESSL, and as of June 2026 public access to older data was disabled
in response to abuse. Unusable. Severe convective storm was subsequently dropped from
scope entirely. **Check licence terms before cataloguing a source as available.**

**11.6 — Global building footprints in the ingest.** Briefly implied by "enrich each
event with buildings exposed". 2.7 billion footprints cannot be queried on a timer.
Resolved by making it an on-demand drill-down, which is both feasible and a better
representation of how the work is actually done.

**11.7 — Modelling a provider's SLA.** An elaborate two-axis severity-versus-contract-clock
scheduling model was proposed. It rests on numbers nobody outside the provider has. There is a
genuinely interesting finding here — Copernicus EMS Rapid Mapping Service Level 1 is
2–12 hours **after image reception**, not after event onset, so the acquisition wait sits
outside the SLA entirely — but knowing that is not the same as being able to model it.
**Out of scope. Do not add an SLA clock.**

**11.8 — Blending humanitarian and economic into one weighted score.** Superficially
tidier, but requires defending weights that have no basis. The two-axis design with a
max rule avoids the question entirely, and the ability to sort by either axis makes the
honesty visible.

**11.9 — Storing every poll.** Would bloat the database with near-identical rows.
Resolved by the rolling window and overwrite-in-place. A change-log design was also
considered and dropped as unnecessary for a "what is happening now" tool.

**11.10 — Letting the app become the project.** The persistent risk. The reasoning
behind the scoring is what demonstrates judgment; the app is how it is shown. **If a
choice arises between a more impressive implementation and a better-reasoned one, take
the better-reasoned one.**

**11.11 — Overclaiming in language.** "Buildings damaged" instead of "buildings
exposed", "people affected" instead of "people exposed". Easy to slip into, and exactly
the kind of imprecision a careful reader will find. Section 6.1 is the standard.

**11.12 — Cutting a source entirely when demoting it would do.** GDACS was briefly
proposed for removal from the project altogether once the other sources were settled.
That was an overcorrection. It costs almost nothing to ingest and store something whose
usefulness is uncertain; it costs a retrofit to add it back later. **Demote and store
before you delete.** The reverse error is also live — see 11.13.

**11.13 — Promoting a newly found source to "primary" without checking what it
displaces.** NSI was initially proposed as the *primary* exposure layer. It is not.
Population and buildings already had good answers; NSI fills the economic hole
specifically. A new source that solves one problem well should be scoped to that problem,
not allowed to expand into areas that were already handled. **Before calling anything
primary, name what it replaces and check that thing was actually inadequate.**

**11.14 — Importing SAR instinct.** The rest of the portfolio is SAR change detection,
and there is a recurring tendency to over-import prior-project complexity into problems
where it does not belong. This
project touches no imagery.

---

## 12. Open decisions — none of these are decided

| # | Decision | Blocks |
|---|---|---|
| O1 | **RESOLVED 2026-08-28.** Per source: 14 days by age for earthquake/GDACS; by presence for wildfire (3 days unseen) and wind (2 days). See DECISIONS.md and PROGRESS.md | Database schema |
| O2 | Poll frequency per source | Ingest jobs |
| O3 | **RESOLVED 2026-08-25.** Enrich (PAGER + ShakeMap) only when USGS `alert` is non-null, using PAGER's own judgment rather than an invented magnitude cutoff | Phase 1 |
| O4 | **RESOLVED 2026-08-25.** Continuous log scale, 10,000 people exposed = 50 (GDACS wildfire threshold, generalised as a stated assumption). See `backend/app/scoring.py` | Phase 3 |
| O5 | **RESOLVED 2026-08-25** (occupancy-mix weighting not used). Continuous log scale, PCS US$25M = 50, NSI structure + content replacement cost. Original question: economic score formulation from NSI replacement cost — whether occupancy mix weights it, and how the replacement-cost-versus-insured-value gap is communicated | Phase 3 |
| O6 | **RESOLVED 2026-08-23.** Earthquake: USGS PAGER's own LandScan-based exposure, no separate computation. Wildfire/wind: NSI's own population figures, single count, no day/night switching (dropped as false precision). See sections 5.6 and 6.3 | ~~Phase 1~~ done |
| O7 | How confidence is represented and displayed | Phase 3 |
| O8 | Building source — VIDA merged, or OpenBuildingMap, or both compared | Phase 4 |
| O9 | Whether to add FIRMS as a secondary signal for very new fires with no perimeter | Phase 2 |
| O10 | **RESOLVED 2026-08-23.** Plain Postgres, WKT/GeoJSON + shapely, not PostGIS — local geometry volume is small, heavy work happens against externally-filtered data. See section 8.1 | ~~Phase 1~~ done |
| O11 | **RESOLVED 2026-08-22.** Mirror WildfireDashboard: FastAPI on Railway; React/Vite on S3 + CloudFront (frontend hosting not yet provisioned) | Phase 5 |
| O12 | **RESOLVED 2026-08-22.** `NatCatDashboard`, flat `backend/` + `frontend/` | Repo scaffold |
| O13 | Whether the per-event display includes a generated plain-language summary | Phase 5 |
| O14 | Whether stored GDACS data gets used for anything — a published humanitarian cross-check, a validation check against our own computed population figures, or nothing | Deferred; nothing blocks on it. The data accumulates in the meantime |
| O15 | **Raised 2026-11-14.** Whether to add a supplementary (possibly temporary) method for retaining or back-filling older events if live data proves too thin to work with. Live data stays the primary mode (D2 unchanged); this would supplement it, not replace it, and would touch D10's rolling window. Decide only after a fresh ingest shows what live data actually looks like, and after checking what history each source holds (USGS catalogue by date, NIFC year-to-date/archive perimeters, NHC advisory archive, GDACS date-range search) | Phase 5 usefulness; not blocking yet |

---

## 13. Stated assumptions and genuine unknowns

Recorded so they are never silently guessed:

- **Commercial providers' actual SLA durations, where their clock starts, and how they
  weight contractual obligation against event severity.** Not publicly available. Not
  modelled.
- **How a provider prioritises between a commercially significant and a humanitarianly
  significant event competing for the same analyst hours.** Unknown. The two-axis design
  is a deliberate refusal to guess.
- **Insured value as a spatial layer.** Does not exist openly. Economic scoring uses
  proxies and must say so.
- **Whether commercial providers use interferometric coherence for earthquake
  products.** Inferred from pre-imaging language, never stated. Must not be asserted.
  Relevant only if the write-up discusses what happens downstream of triage.
- **The GDACS wildfire area threshold.** Verified 2026-08-23 (Phase 0): the 10,000 ha
  homepage-display filter is real, but so is an explicit manual-override path for
  smaller urban-adjacent fires, which is how GDACS actually flagged the LA wildfires.
  See section 5.4 for the corrected finding.
- **Whether Google confidence scores survive the VIDA merge.** Verified 2026-08-23: the
  field survives, but has zero populated rows for the United States — Google Open
  Buildings V3 deliberately excludes the US and Europe from its coverage. Not usable
  for this project's scope; see section 7.2 and `DECISIONS.md` (Phase 0 verification findings).
- **NSI's current data vintage and the licensing position on the base layer.** Vintage
  verified 2026-08-23: current release is NSI 2026 Base, population indexed to April
  2025, prices to August 2025 — not stale. Licensing position still not fully resolved:
  current technical documentation lists source datasets with no mention of CoreLogic,
  but this isn't a substitute for an explicit licence statement if redistribution
  (rather than read access) ever matters. The 2019 release indexed population to 2017
  and prices to 2018; the current 2026 Base layer supersedes it.

---

## 14. Related project files

If additional context is wanted beyond this document, these help:

- **NatCat_Data_Reliability_Reference.md** — failure modes for population, DEM and road
  data. The essential population content is summarised in section 5.5 but the full
  document is worth reading before the QC work. **Recommended.**
- **NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md** — the research this plan came from,
  including material deliberately excluded here. Useful for the write-up, not needed for
  the build. **Optional.**
**Keep SAR methodology material out of a build context.** It would push this project
toward the mistakes recorded in sections 11.2 and 11.14.

---

## 15. Progress log

**2026-08-22** — Project scoped. Two rounds of background research completed covering
the operational analyst role, industry triage practice, the insurance and reinsurance
customer side, and data source verification. Two-stage industry workflow confirmed from
commercial SAR providers' published material. Sequencing settled: this runs first,
imagery-based work stays separate. Sources settled: USGS, NHC, NIFC, with GDACS demoted to comparison baseline
after discovering it has no structured earthquake exposure and too high a wildfire
threshold. Scoring settled as two axes with a max rule. Building footprint methodology
settled as an on-demand three-count comparison with disagreement classification.
Fourteen open decisions registered, none resolved. Fourteen rejected approaches recorded
in section 11.

Late in the same session, two further changes. GDACS resolved to ingest-and-store rather
than either full integration or removal — its use is deferred to O14, on the grounds
that storage is cheap and retrofitting is not. And the National Structure Inventory
added as an additional source after the economic axis was identified as the weakest part
of the plan; it is scoped to that axis specifically and is a candidate, not the assumed
answer, for population (O6).

Next action: Phase 0 verification.

**2026-08-23** — Phase 0 verification complete (full detail in
`DECISIONS.md` (Phase 0 verification findings)). Two corrections to this document's original claims, both
made in place above rather than reconstructed after the fact:

Section 5.4's central GDACS-wildfire claim was wrong as originally written. GDACS did
not miss the LA wildfires — it flagged both (Palisades, Eaton) at Orange on their
actual ignition dates, via a manual-override path for urban-adjacent fires that the
original research had not found. The corrected, verified finding is sharper than the
original hypothesis: GDACS tracked the event but never escalated past Orange despite it
becoming the costliest wildfire in US insurance history, because its wildfire severity
metric (burned hectares) is structurally decoupled from structure value. Section 7.2's
claim that Google's confidence scores could be applied as a fourth building-count
filter also doesn't hold at this project's scope — confirmed live against the actual
USA data that Google Open Buildings has zero coverage in the United States (by design;
its stated scope is Africa, South Asia, Southeast Asia, and Latin America/Caribbean).

Everything else in sections 5.1–5.3 and 5.6 (USGS, NHC, NIFC, NSI) verified largely as
assumed, with implementation-level refinements: USGS's loss/exposure data is direct
JSON, no PDF-scraping needed; NHC's real feeds live at per-basin `.xml` paths rather
than `gis/rss.php` (a landing page), and `CurrentStorms.json` is a materially better
polling target than RSS, covering all basins in one structured call; NSI's bbox query
needs a closed polygon ring rather than a simple bbox, and its current vintage (2026
Base) resolves the staleness concern this document originally flagged. Nothing found
in Phase 0 changes the project's scope or the decisions in section 10.

Next action: Phase 1 — the earthquake-only vertical slice.

**2026-08-23 (later same day)** — Post-Phase-0 design discussion resolved three
things. First, confirmed the building footprint methodology (section 7.4) was already
settled, not open — four parallel counts plus disagreement classification, no single
primary source; the only change from Phase 0 is B (union) now spanning two sources
(OSM+Microsoft) instead of three for this project's US scope. Second, decided (section
5.2) to ingest both NHC's per-basin RSS feeds and `CurrentStorms.json` rather than
replacing one with the other — same demote-don't-delete logic as GDACS, decide which
to keep once real ingested data is in hand. Third, **O6 resolved**: dropped the
day/night population switch entirely as false precision; earthquake population exposure
comes from USGS PAGER (LandScan-based internally, no separate computation);
wildfire/wind population comes from NSI's own figures as a single count. The NSI choice
was verified empirically against a real sparse rural area (Arthur County, Nebraska) to
confirm it doesn't inherit the flat-rate-over-large-polygon problem that affected
`WildfireDashboard`'s Census-tract population data — confirmed it doesn't, because NSI
is point-based (per-structure) rather than polygon-averaged.

Next action: Phase 1 — the earthquake-only vertical slice.

**2026-08-25** — Phase 1 backend complete and verified against live data end to end,
including the real deployed infrastructure, not just local testing. Railway
provisioned: a Postgres service (public TCP proxy for local dev, private
`DATABASE_URL` reference for the deployed backend) and the backend itself deployed as
a second service in the same project (root directory `backend`, Nixpacks + the
existing `Procfile`, no Dockerfile). Live at
https://natcatdashboard-production.up.railway.app.

Built: `raw_usgs_events` (raw table, USGS's own structure, two-tier PAGER
enrichment screened on `alert` non-null rather than an invented magnitude cutoff -
O3 resolved this way); the unified `events` table with normalisation
(`normalize_to_events`); a first, deliberately thin scoring pass that bands PAGER's
own already-published fatality and economic-loss numbers using PAGER's own
thresholds, kept as genuinely separate humanitarian/economic axes with
`overall_score` as the max of the two, scoring only the minority of events with a
PAGER product and leaving everything else honestly null rather than fabricated;
`POST /api/ingest/usgs` running the whole chain (fetch → raw upsert → normalise →
score); `GET /api/events` returning the result ranked by `overall_score`, nulls last.

Verified against real USGS data throughout, not mocked, both locally and against the
actual Railway database: ~392 US earthquakes ingested, the 4 with PAGER products
correctly scored and correctly ranked above the ~388 without one. Confirmed the
deployed backend (not just local dev) can reach Postgres via the internal
`DATABASE_URL` reference by hitting the live endpoints directly.

Two deliberate, documented gaps carried forward rather than solved prematurely: no
real hazard footprint geometry yet for earthquake (would need USGS's ShakeMap MMI
contours, not fetched - `footprint_geojson` exists in the schema but stays null until
Phase 3 actually needs it for NSI intersection), and no rolling-window pruning yet
(the raw table only ever grows for now - deferred to Phase 2 alongside real
scheduling, per the plan's own destructive-action care requirement in section 8.1).
Caught and fixed one real bug along the way: `migrations/env.py` never actually
imported `app.models`, so the first autogenerate attempt for each new table came back
silently empty - worth remembering if a future migration ever looks suspiciously
empty again.

Only remaining Phase 1 item is wiring real data into the frontend placeholder page
(the "minimal display" in Phase 1's own definition) - not yet done. Frontend
deployment (S3/CloudFront) also still open, deliberately deferred until there's a
reason to need it live.

Next action: Phase 1(e) - wire real earthquake data into the frontend, or move
straight to Phase 2 (remaining perils) if the placeholder page is judged sufficient
for now. Sam's call.

**2026-08-25 (continued)** - Decided to defer frontend wiring rather than do it now:
building it once against real multi-peril data makes more sense than building it
for earthquake alone and revising it twice more as NHC and NIFC come online. Moved
straight to Phase 2, completed the same day.

Built, one source at a time, each verified against live data and the real deployed
database before moving to the next: **NIFC** (wildfire) - `raw_nifc_events` +
normalisation; unlike earthquake, wildfire gets a real footprint polygon from day
one (fire perimeter, with a shapely-computed centroid for the point location), using
the GIS-calculated acreage rather than the self-reported figure since the former
stays internally consistent with the stored geometry. **NHC** (wind) - both
`CurrentStorms.json` and the three per-basin RSS feeds built, per the earlier
"ingest both, decide later" decision - and real data justified that caution rather
than just being caution for its own sake: `CurrentStorms.json` kept a storm (Moke)
tracked as post-tropical-cyclone status while the RSS feed's own headline for the
same storm called it the final advisory - genuinely different information, not
redundant views of the same event. RSS's `<nhc:Cyclone>` elements also carry a
human-readable NHC headline `CurrentStorms.json` has no equivalent for at all.
**GDACS** - raw storage only per D8, scoped to this project's three tracked perils
rather than all seven GDACS hazard types, confirmed never touching the unified
events table (613 rows before and after ingesting 5 GDACS records).

Wildfire and wind scoring deliberately left null rather than reusing earthquake's
Phase 1(d) PAGER-band placeholder - that placeholder only works because PAGER
publishes fatality/economic numbers directly; nothing equivalent exists for
wildfire or wind, and inventing a second one-off scheme per source would be
building the wrong thing twice before Phase 3's real formulation (O4/O5) replaces
all of it anyway.

End state: the unified `events` table holds 613 real events across all three
perils (392 earthquake, 217 wildfire, 4 wind), all ingest paths verified against
live upstream data and the actual Railway database, not mocked at any point.

Next action: Phase 3 - the real scoring formulation (O4, O5), or the deferred
frontend wiring, or continued deployment work (frontend not yet deployed). Sam's
call.

**2026-08-25 (continued)** - Phase 3, O4/O5 resolved. Three real design forks
confirmed with Sam before any code was written, per rule 1: score what's ready now
(wildfire has a footprint; earthquake's humanitarian axis can use PAGER's own
pre-computed exposure without one) rather than block on fetching earthquake/wind
footprint geometry first; continuous log-scale scoring rather than banded/ordinal
(section 6.3's "weighted by hazard intensity" read as a genuine intensity weighting,
not just a threshold crossing); economic axis anchored to PCS's real $25M US
catastrophe-designation threshold (section 4.1) rather than an unanchored scale.

The humanitarian axis needed a second real anchor, since PCS's threshold is
specifically economic. None of the researched sources publish a population-exposure
threshold outside a specific hazard context - the only one found was GDACS's own
wildfire homepage-display criterion (population within 5km exceeding 10,000,
section 5.4). Generalised across all three perils as the humanitarian axis's
reference point. This is a stated assumption, not a perfect fit borrowed from an
identical context, and worth revisiting if a better cross-peril anchor turns up.

Earthquake's humanitarian score now uses PAGER's own MMI-banded population
exposure, weighted by intensity (MMI 4+, weight = mmi-3) - a genuine improvement
over Phase 1(d)'s placeholder, which just banded PAGER's fatality numbers directly.
Verified against live data: a M3.84 earthquake near dense San Leandro/Bay Area
population scored highest (98.7) of four live events, above a M5.2 quake in sparse
rural Hawaii (38.1) - the humanitarian axis measuring population exposed rather
than magnitude, which is exactly the generalised point behind section 4.5's
Myanmar/Thailand divergence example, now showing up in a live result rather than
just the write-up's worked examples.

Wildfire's economic and humanitarian axes now run via real NSI point-in-polygon
intersection (`nsi.py`) - genuinely expensive-tier, so kept separate from
normalisation with a change-detection guard (only rescore if never scored or the
perimeter changed) and a per-call limit, the same cheap-screen/expensive-enrich
discipline already used for PAGER and the (still Phase 4) building footprint work.
Caught and fixed a real bug while building this: normalisation was unconditionally
resetting scores to null on every poll, which would have silently erased anything
the scoring pass computed - fixed to preserve existing scores during normalisation.

Wind scoring deliberately not built - no footprint geometry exists for it yet,
consistent with the sequencing decision above.

Next action: build footprint geometry for earthquake (ShakeMap MMI contour) and
wind (wind radii / track cone polygon) so their economic axes can be scored too,
or the deferred frontend wiring, or frontend deployment. Sam's call.

**2026-08-26** - Earthquake's footprint geometry and economic axis built, using
USGS ShakeMap's `cont_mmi.json` contour product. Real contour data turned out
messier than expected: fragments aren't reliably closed rings (roughly two-thirds
closed on a real M7.4 event checked live) - only closed rings are used, unioned
into a polygon for the area shaking at or above MMI 4.0. `score_economic()` mirrors
wildfire's expensive-tier, guarded pattern from Phase 3, but only ever touches the
economic axis - humanitarian stays owned by the cheap PAGER-based pass, since NSI's
population figure would be a worse substitute for PAGER's own MMI-weighted
exposure, not an improvement.

A real bug surfaced and was fixed during verification, not just a design note this
time: SQLAlchemy's `JSON` column type stores Python `None` as the JSON value `null`
by default, not SQL `NULL`, so a SQL-level `IS NOT NULL` filter on `footprint_geojson`
matched every earthquake row rather than just the ~4 with real geometry. Caught
because the candidate count (58) didn't match the known PAGER-covered count (4) -
worth noting as a reminder that verification means checking whether numbers make
sense against what's already known, not just checking for a successful response.
Fixed by filtering in Python after fetching instead; 20 rows that had already been
touched with a misleading confidence message were reset directly. Full detail in
`DECISIONS.md`.

Wind's footprint geometry (wind radii / track cone polygon, from NHC's linked GIS
products) is not yet built - wind still has no scoring on either axis.

Next action: wind footprint geometry, or the deferred frontend wiring, or frontend
deployment. Sam's call.

**2026-08-27** - Wind's footprint geometry and scoring built, completing Phase 3's
original scope: all three perils can now be scored on both axes where data
supports it. Uses NHC's `initialWindExtent` wind radii shapefile (current radii,
not forecast). Both axes scored via NSI, unlike earthquake - wind has no
PAGER-equivalent published humanitarian baseline to draw on.

Real-format detour worth recording: the KMZ product looked simpler at first but
GDAL's KML driver reported this layer's geometry as "Unknown" and silently
returned no geometry via `pyogrio`'s low-level reader - no error, just nothing. The
shapefile equivalent correctly reported `Polygon` geometry, but even then the same
low-level reader returned nothing; only the higher-level `geopandas`-integrated
path worked, which is why `geopandas` is now a dependency - added because a lower
layer proved unreliable, not by initial preference. Also confirmed live that
GDAL's combined remote-read virtual filesystem, which worked fine for VIDA's
FlatGeobuf in Phase 0, took 30+ seconds for a wind radii file under 4KB - switched
to a plain download instead.

Verified against live data: the one currently active storm (Lala) got a real
footprint and a real NSI score (0 structures - correctly zero, since Lala sits
over open Pacific far from any US land, not a failure). This project's
cheap-screen/expensive-enrich discipline didn't need applying here the way it did
for earthquake and wildfire - active storm counts are always small (typically 0-5
globally), so wind radii are fetched for every storm on every poll without a
guard.

Next action: the deferred frontend wiring, frontend deployment, or rolling-window
pruning (increasingly worth doing now that stale rows from superseded polls are
visibly accumulating across all three perils). Sam's call.

**2026-08-28** - Rolling-window pruning built, O1 resolved. Real design fork worked
out before writing any deletion code: a single age-based rule would have been a
genuine bug, not just an approximation - a wildfire's discovery date can be weeks
old while it's still actively burning today, so pruning by event age would delete
still-current incidents. Split by source instead: age-based (14 days) for
earthquake and GDACS, which are already fetched as a bounded time window; presence-
based (not seen in a poll for 3 days wildfire / 2 days wind) for wildfire and wind,
where absence from the source's own current-state feed is what actually means an
incident is over.

Followed the plan's own safety requirement for destructive routines rather than
treating it as a formality: built with a mandatory dry-run mode (deletion only runs
when explicitly requested), ran the dry-run against the real database first,
reviewed the specific numbers together (including spot-checking that a flagged
candidate was genuinely 16 days old against the 14-day rule, not a miscalculation),
and only ran it for real after explicit approval. Verified afterward by querying
the database directly rather than trusting the response - row counts dropped by
exactly the predicted amounts, and a specific deleted row was confirmed actually
gone from both its raw table and the unified table.

Also encountered, mid-session, a real operational lesson worth recording: the
Railway project hit its usage/cost limit while this work was in progress, which
manifested as both the deployed backend and the database becoming unreachable at
once - "Application not found" from Railway's own routing layer, not an error from
our own code. Diagnosed by checking DNS resolution and the deployed service
directly to confirm it wasn't a local network issue before concluding it was
Railway-side, rather than guessing. Resolved by Sam raising the limit temporarily.

Not yet wired into the automatic ingest endpoints - still a manual, reviewed
trigger by design, until it's been run for real more than once.

Next action: the deferred frontend wiring, or frontend deployment. Sam's call.
