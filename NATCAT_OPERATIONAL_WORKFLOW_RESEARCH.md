<!-- NATCAT_OPERATIONAL_WORKFLOW_RESEARCH.md -->

# NatCat Operational Analyst Workflow — Research and Project Scoping

Created: 2026-08-21
Revised: 2026-08-22 (research round 2 — insurance/reinsurance customer side,
commercial EO product verification, data source verification, API structures)
Status: HISTORICAL RESEARCH. Written before the project was chosen. Every open question
here has since been resolved in NATCAT_TRIAGE_PROJECT_PLAN.md, which takes precedence
wherever the two differ. Kept as source material for the write-up.
Related: NatCat_Data_Reliability_Reference.md (data failure modes).

---

## 0. The premise being tested

Hypothesis: the SAR analysis in the existing portfolio, while good, is not the core
skill a NatCat operations analyst role in commercial Earth observation actually tests. The role is largely about
ingesting fast, widely-available hazard data, assessing events quickly, and assigning
priority — with SAR tasking downstream of that judgement rather than the substance of
the job.

**Round 1 supported this. Round 2 supports it more strongly, and adds a correction:**
the commercial triage logic this project would build is not an unexplored gap. It is
existing, documented industry practice with published thresholds. That changes the
project's framing — see section 4 and section 9, tension 1.

---

## 1. What the role actually is — direct evidence from job listings

Multiple published NatCat operations analyst listings in commercial Earth observation
(several locations, a wildfire variant, and a remote variant) describe the same shape
of work:

- The delivery team is responsible for **24/7 monitoring and analysis
  operations** enabling near-real-time assessment of global natural catastrophes
- **Monitor and analyse diverse earth observation datasets to track live NatCat
  events** (variants specify flood, wildfire, or generic "live events")
- **Responsible for activation, verification and delivery of the analysis output to
  customers in accordance with SOP while adhering to the established quality standard
  and service level agreement**
- **Manages own workload effectively, reprioritising based on changing requirements;
  cooperates with the Delivery Lead on planning and prioritising work** (some listings
  name a delivery manager rather than a delivery lead)
- Performs quality checks and provides feedback on errors in analysis and delivery;
  contributes to quality improvement through documenting errors and outages
- Execute structured geospatial workflows by integrating various spatial inputs and
  analysis methodologies
- **Conduct flood meetings and prepare operational plans**
- **Conduct data research and perform social media data analysis**
- Monitors metrics and contributes to KPI reviews
- Devise and execute quality control measures to detect and correct output
  inconsistencies

Desirable: operational GIS role experience, Python, AWS CLI, PostgreSQL, familiarity
with real-time geospatial data sources and disaster monitoring tools, and — as a plus
rather than a core requirement — SAR experience.

### 1.1 Two details found in round 2 that change the design (NEW)

**Coverage is follow-the-sun, not a single 24/7 desk.** A US listing describes working
in US time zones while collaborating with colleagues across time zones spanning North
America, Europe and Asia.

This matters more than it looks. 24/7 monitoring is achieved by regional shifts with
handover, which means the work queue is not a private ranking held in one analyst's
head — it is **shared state that has to survive a handover**. A prioritisation model
that assumes one continuous operator is modelling the wrong thing. No portfolio project
in this space models handover. It is a genuine differentiator and a genuine source of
operational-judgment scenarios (what do you hand over, in what state, with what
caveats).

**Independent issue resolution is stated in the job description.** One listing:
"Proactively raises issues and suggests resolutions, **resolves small scale operational
issues independently**." Independent judgment is written into the role, not
inferred.

---

## 2. The contractual-vs-severity question

The listings put SLA as the hard constraint ("in accordance with SOP while adhering to
the established service level agreement") with severity-driven judgement operating
*within* it ("reprioritising based on changing requirements"). KPI reviews imply
on-time delivery is measured; analyst-level reprioritisation implies queue order is not
purely mechanical.

Round 1 concluded this is a two-axis scheduling problem: contractual clock versus
impact severity. **Round 2 says that is under-specified in two ways.**

### 2.1 The SLA clock does not start when the event starts (NEW)

Copernicus EMS Rapid Mapping is the closest public analogue with a published service
level, and its Service Level 1 is: production 24/7/365, **delivered within 2–12 hours
after image reception**. Service Level 2 is working days, 1–5 working days after image
reception.

The clock starts at *image reception*, not at event onset. The acquisition wait — which
is usually the dominant latency — sits outside the SLA entirely.

If this pattern holds commercially (unverified for commercial providers, see section 8), an event is
not in one of two states but at least three:

1. **Detected, awaiting data.** No SLA clock running. Priority here is a *tasking*
   decision, not a delivery decision.
2. **Data in hand, SLA clock running.** Priority here is a *delivery* decision.
3. **Delivered, monitoring for update.** Re-visit cadence applies.

Conflating these produces a model that penalises the analyst for satellite revisit
time. That is a modelling error worth avoiding explicitly, and worth stating in a
write-up, because it is exactly the kind of thing that separates someone who has
thought about operations from someone who has drawn a Gantt chart.

### 2.2 Re-visit cadences are themselves contractual (NEW)

PCS re-surveys on a fixed clock — Canada and Mexico every 60 days, APAC every 90 days,
until a final estimate. Commercial SAR providers' published cadences are much faster (flood extent
every 6 hours; wildfire every 24 hours through fire duration; hurricane within 24 hours
of landfall). Either way, a delivered event does not leave the queue. It re-enters it
on a schedule. A queue model with only "pending" and "done" is wrong.

**Remaining genuine unknown:** a commercial provider's actual SLA durations, where their clock starts,
and how they weight contractual obligation against event severity. Not publicly
available. Treat as a stated assumption, not a guess. Stating it as a known unknown is
a stronger position than inventing a number.

---

## 3. How the industry already does automated triage

Two mature public systems do humanitarian-weighted scoring. Both should be used as
comparison baselines rather than reinvented.

### 3.1 GDACS

Run by the European Commission JRC with DG ECHO, in partnership with the UN. Seven
hazards: earthquakes, tsunamis, tropical cyclones, floods, volcanoes, droughts, forest
fires. **Renamed to Global Disaster *Awareness* and Coordination System in November
2025** — same acronym, worth getting right in a write-up.

**Scoring logic.** Combines event parameters with population exposure, vulnerability,
and **country-level coping capacity** to produce a continuous score plus a colour band.
The coping-capacity term is the important one: GDACS asks *will this exceed national
response capacity*, not *how big was it*.

**Alert bands.** GREEN 0.1–0.99, minor or potential impacts, unlikely to require
international humanitarian aid. ORANGE: severe, potential serious impacts requiring
some international humanitarian response. RED above that.

**Hazard-specific thresholds.** Floods: orange above 100 dead or 80,000 displaced; red
above 1,000 dead or 800,000 displaced. Forest fires: all ongoing orange/red events,
plus green where burned area exceeds 10,000 ha and population within 5 km exceeds
10,000. Tsunami scenarios: orange at 1–3 m predicted wave height near populated coast,
red above 3 m.

**Forecast-uncertainty handling, worth stealing.** TC impact reports up to five days
before landfall, with forecast uncertainty propagating into the score. To avoid alert
churn, **red alerts forecast more than three days ahead are automatically downgraded to
orange.** An explicit, documented design decision about confidence versus lead time.
They also note a cyclone alert moving red to green within 48 hours on slight track
changes is not unusual. Alert volatility is a known, accepted property.

**Change detection is built in.** The homepage bolds events that are new, that have
significantly worsened (defined as +0.5 GDACS score or an alert level increase), or
that have new information products. A ready-made model for "what changed since I last
looked" — and, per section 1.1, for what a shift handover should surface.

**Exposure basis (NEW).** GDACS uses the Global Human Settlement Layer (GHSL) for
population exposure across all hazards, via the Copernicus EMS Exposure Mapping
component. It also publishes, per event, a list of potentially exposed **critical
infrastructure**: power plants, airports, ports and dams. That critical-infrastructure
list is a commercially relevant field that round 1 missed.

**Independent validation.** A 2020–2024 global analysis found the GDACS score
correlated with earthquake deaths at rho 0.522 and predicted field-hospital deployment
strongly (AUC 0.98). Field hospitals deployed in 52.9% of red events and 0% of orange.
The study notes GDACS is hazard- and exposure-centric and cannot capture mediators like
collapse dynamics or health-system resilience, recommending it be treated as a
**first-layer signal complemented by rapid damage assessment.** That framing — triage
layer first, SAR assessment second — is the workflow being replicated here, stated by
an independent source.

### 3.2 USGS PAGER

Earthquake-only, but methodologically the closer analogue for an insurance customer
because it estimates **economic loss** alongside fatalities.

**Dual-threshold logic.** Alert level is whichever metric is worse.
- Fatalities: yellow at 1, orange at 100, red at 1,000
- Economic loss: yellow at $1M, orange at $100M, red at $1B

**Alert meaning is response-scale, not severity.** Green: little or no impact. Yellow:
regional. Orange: national. Red: international response required.

**Why the dual approach exists.** High fatality counts dominate where local building
practice produces high collapse rates, and those drive international response —
economic loss dominates elsewhere. The 2010 M8.8 Chile earthquake triggered red on
projected economic loss but only orange on estimated fatalities. That divergence is the
whole point, and it is the same divergence this project would generalise.

**PAGER preserves uncertainty explicitly**, publishing a histogram of the likelihood
that adjacent alert levels are correct. If green and yellow are comparable in
likelihood, the model cannot distinguish them and says so. Directly reusable pattern
for honest confidence communication.

**Base rates.** Over 38 years: roughly 17,792 green, 568 yellow, 52 orange, 49 red.
Orange-or-above is roughly one and a half events per year. Any triage system must be
designed around that base rate or it will drown in green.

**Known limitation:** PAGER does not account for secondary effects — landslides,
liquefaction, tsunami — in its loss estimates.

---

## 4. The commercial side — what round 1 missed

This is the substance of round 2. Round 1 asserted that insurers care about something
close to the inverse of GDACS. That is correct, but it framed the divergence as an
unexplored gap. It is not. **The industry has published designation thresholds,
published product timelines, and an automated event-response layer that already
consumes commercial SAR data.**

### 4.1 PCS catastrophe designation — a real, published triage gate

PCS (Property Claim Services, a Verisk unit) designates catastrophes and assigns serial
numbers that the market uses to track losses and to trigger reinsurance and ILS
contracts.

**Designation is a three-test gate, all three required:**
1. Expected insured loss greater than the regional threshold
2. The event is deemed likely to impact **the majority of the insurance market**
3. The event is likely to result in **a significant number of claims** for the industry

Note what tests 2 and 3 do: they are *not* severity. A single very large loss to one
insurer does not qualify. Breadth across the market matters as much as depth. That is a
genuinely different shape of criterion from anything in GDACS or PAGER, and it is
directly usable in a scoring design.

**The monetary threshold varies enormously by region:**

| Region | Designation threshold |
|---|---|
| United States | US$25M |
| Canada | C$25M |
| Mexico | MX$300M (resurvey above MX$950M) |
| Turkey | ₺10M |
| Japan | US$2bn |
| Rest of APAC | US$2.5bn |

The US threshold has been $25M since 1997 ($5M 1982–1996, $1M before that).

**This table is the divergence argument in published form.** The industry does not
apply one global severity bar. It applies a bar calibrated to how much insured value is
there to lose. An event in Japan needs to be eighty times larger in loss terms than an
event in the US to get a serial number. A humanitarian system would never do that. This
is much stronger evidence for the project's thesis than the theoretical argument in
round 1, because it is someone else's published decision rule, not an assertion.

**Resurvey cadence:** Canada and Mexico every 60 days, APAC every 90 days, until a
final estimate. Events do not leave the queue on delivery.

**Scope note:** PCS US excludes NFIP-covered flood losses — a reminder that "insured
loss" is defined by what the private market actually covers, which varies by peril and
country.

### 4.2 Aon Impact Forecasting — Automated Event Response (AER)

The clearest published picture of what a cat modelling team does during a live event.

**Timeline.** Customised AER reports are sent to each insurer automatically **within 30
to 60 minutes of a new forecast being issued**, before landfall. The trigger is a new
forecast cycle, not a human decision. Aon's Event Analytics platform (relaunched
September 2025) wraps AER with mapping and historical recast.

**Peril coverage, which is itself informative:**

| AER product | Data basis |
|---|---|
| US Hurricane | Latest forecast data including AI-driven hurricane models |
| Japan Typhoon | Track forecasts, several hours before landfall |
| Australia Cyclone | Event-driven, no manual intervention |
| European Windstorm | Multiple European met agencies plus gust observations from 4,000+ stations |
| European Hail | Hail observations, post-event |
| US Severe Convective Storm | Daily loss and claims-count estimates during and after |
| Global Flood | **Flood extent data from a commercial SAR provider**, plus a 4-day forward flood risk indication |
| US Wildfire | **Building damage estimates from a commercial SAR provider**, giving near-real-time exposed limit |
| Australia Bushfire | Near-real-time perimeters from the Digital Atlas of Australia |

**Two things to take from this.** First, a commercial SAR provider is a named upstream data supplier inside
a broker's live loss-estimation product for two perils. The customer for the analyst's
output is not an abstract insurer — it is, at least sometimes, another firm's automated
pipeline with its own clock. Second, the industry does not treat "wind" as one peril
(see section 9, tension 7).

**Stated AER use cases:** estimating impact on particular portfolios; resource
allocation and decision making; claims adjustment; live cat and industry loss warranty
products; benchmarking other estimates. The ILW use case matters — it means loss
estimates feed instruments that pay out on index triggers.

**Adoption context:** Aon's 2025 Catastrophe Risk Management Survey found only 54% of
insurers use catastrophe models to guide response strategies.

### 4.3 McKenzie Intelligence Services — the direct competitor, and FNOI

MIS operates the Global Events Observer (GEO) platform for the Lloyd's market. **Verisk
acquired MIS in July 2026** — recent consolidation directly in this space.

The concept worth stealing is **FNOI versus FNOL**. The industry norm is First
Notification of Loss: the policyholder reports damage. MIS sells First Notification of
Incident: telling the insurer about damage *before* it is reported.

That reframes what triage is optimising for. It is not "which event is worst." It is
**"where does knowing early create the most value over the insurer finding out
anyway."** Those differ. An event in a region with fast, functioning claims reporting
generates FNOL quickly on its own; an event that knocks out communications, or that
affects commercial property with slow reporting chains, has a much larger FNOI-FNOL
gap. This is a candidate scoring term that nothing in GDACS or PAGER contains.

MIS also states confident claims resolution **within 48–72 hours** of an event, and
uses an AI damage classifier followed by **manual assessment by trained imagery
analysts**. That human verification step is the *verification* in
activation-verification-delivery, described publicly by a competitor.

### 4.4 Parametric triggers — a third urgency axis

Trigger taxonomy for parametric and ILS instruments:

- **Pure parametric:** payout on a physical measurement — wind speed, magnitude,
  rainfall depth
- **Modelled loss:** payout on a cat model's estimate for the event
- **Industry loss index:** payout on an industry-wide figure, typically PCS. This is
  what an industry loss warranty (ILW) uses
- **Indemnity:** payout on actual assessed loss
- **Cat-in-a-box:** trigger requires the event meeting the index to occur inside a
  pre-agreed polygon
- **Intensity model:** trigger on measured intensity at the insured location rather
  than a broad box (e.g. Swiss Re STORM for tropical cyclone; New Paradigm's Shake and
  Pay for earthquake shaking)

**Basis risk** — the gap between index payout and actual loss — is the central design
problem, and is why multi-trigger, tiered and sequential structures exist.

**Why this matters for triage.** A parametric or ILS position turns a *threshold
crossing* into a commercially decisive moment independent of absolute severity. An M6.4
that crosses a cat-in-a-box magnitude threshold is more commercially urgent than an M7.5
that does not. This suggests a third scoring axis beyond severity and SLA — call it
**trigger proximity** — that has no analogue in humanitarian scoring at all.

This is a design *option*, not a decision. It has a real cost: actual trigger locations
and thresholds for live instruments are not public in usable form, so any
implementation would be illustrative rather than real. (Since ruled out: see the plan,
section 3.)

### 4.5 Insured versus economic loss by region — the quantified divergence

Swiss Re sigma 1/2026 (published March 2026, covering 2025):

- **190 natural catastrophe events globally**, USD 107bn insured, USD 220bn economic —
  a record 49% insured share, against a 10-year average of about 42% insured
- **Emerging economies: 80–90% of catastrophe losses uninsured**
- **Asia: 30% of global economic losses, about 5% of global insured losses.** Only 8%
  of Asian economic losses were insured in 2025, against a 10-year regional average of
  17%
- Modelled protection gap USD 424bn in 2025 (up from 395bn), resilience index 27.3%,
  improved from 25.3% in 2015
- Long-run insured loss growth 5–7% per year in real terms

**Individual 2025 events, each a usable worked example:**

| Event | Humanitarian read | Commercial read |
|---|---|---|
| LA wildfires (Jan) | Burned area below CA 10-year average | **USD 40bn insured, costliest wildfire on record.** Nearly 3x the recent CA average structure loss |
| Myanmar M7.7 | ~3,900 deaths, USD 11bn economic, minimal insurance | Near-irrelevant to insurers *in Myanmar* |
| Same Myanmar event, Thailand | Far fewer casualties | **USD 1.5bn insured**, because Bangkok's soft-sediment basin amplified shaking |
| Hurricane Melissa (Jamaica) | Jamaica's costliest catastrophe on record, USD 8.8bn total | Only a fraction insured |
| US severe convective storm | Not a GDACS hazard category at all | **Over USD 50bn insured for the third consecutive year**, with no US hurricane landfall |
| SE Asia monsoon flood | USD 11bn+ economic across Thailand/Indonesia/Malaysia | Global insured flood loss for the whole year was USD 3.4bn |

**The Myanmar/Thailand pair is the single best worked example available.** One
earthquake. Humanitarian triage points at Myanmar. Commercial triage points at
Thailand. Neither is wrong; they are answering different questions. If this project
needs one case to carry the argument, that is it.

**The SCS row is the second best**, and structurally more damning: severe convective
storm is not a GDACS hazard type. A monitoring system built on GDACS alone is blind to
the peril that has produced over USD 50bn of insured loss annually for three years
running.

---

## 5. Data source catalogue — verified 2026-08-22

Verification status is stated per source. Where it says "not verified," it means not
verified, not "probably fine."

### 5.1 Cross-hazard / triage layer

| Source | What it gives | Status |
|---|---|---|
| GDACS | Multi-hazard score and colour, 7 hazards, population exposure, critical infrastructure list, change flags | **Live, no key.** Endpoints `geteventlist/SEARCH`, `geteventlist/EVENTS4APP`, `geteventdata`, `getgeometry`; Swagger at `/gdacsapi/swagger/index.html`. Max 100 records per call, ordered by `todate` descending, paging via page size and page number. Attribution required. **Caveat: documented SEARCH URLs returned HTTP 400 from this session's fetch tool. This is more likely a header/user-agent artefact than an outage — an independent API directory listed gdacs.org as reachable with 26 endpoints in March 2026 — but it must be confirmed with a real HTTP client before any design depends on it.** |
| USGS earthquake API | See 5.2 | **Live** |
| Copernicus EMS Rapid Mapping | Activation list, product types, published service levels | Live. SL1 2–12 h after image reception, 24/7/365. SL2 1–5 working days. Products: Reference (pre-event), First Estimate, Delineation, Grading, plus an online report. Activation = one event + one location; multiple AOIs per activation |
| International Disaster Charter | Activation list, dates, hazard, country | Not re-verified this round |
| ReliefWeb | Situation reports, humanitarian updates | Public API, not re-verified |
| EM-DAT | Retrospective disaster losses | Registration required, not real-time |
| MeteoAlarm | Europe-wide official warnings | **Upgraded.** Atom/RSS still available, plus a new API portal at api.meteoalarm.org offering OGC-API EDR 1.0.0, Metadata API v1.0, Hub API v1.0, built under the RODEO project, with a test environment. 38 national met services contribute. Severity moderate/severe/extreme, colour yellow/orange/red. **Quirk: today and tomorrow are issued as separate alerts.** A Redistribution Hub publishes the CAP profile and SLAs |
| PCS | Designation, serial numbers, industry loss estimates | **Commercial subscription (ISOnet PCS). Not open.** Thresholds and methodology are public; the data is not |
| Swiss Re sigma | Annual loss and protection gap by region and peril | Free PDF, annual. Not operational, but the calibration reference |
| Social media | Early signal, ground reports | Named explicitly in operations analyst listings. **Not investigated this round.** Platform API restrictions since 2023 make feasibility genuinely uncertain — treat as an open question, not a source |

### 5.2 Earthquake

| Source | What it gives | Status |
|---|---|---|
| USGS FDSN event API | Real-time GeoJSON, magnitude/depth/location/time | **Live.** `earthquake.usgs.gov/fdsnws/event/1/query`. Bounding box via min/max lat/lon, radius via `maxradiuskm`, filters on magnitude, depth, event type, alert, review status. `count` method available. USGS recommend the pre-built real-time GeoJSON summary feeds over `query` for polling |
| USGS PAGER | Alert level, fatality and loss distributions, MMI exposure | **Live but two-tier.** `properties.alert` in the summary feed carries only the colour, and is **null for most events** — it is populated only where PAGER runs, roughly M5.5+ globally and lower in populated areas. The loss distributions and MMI exposure require fetching the `losspager` product from `properties.products` on a single-event query, which is a second HTTP call per event. **Design consequence: cheap screening on alert colour, expensive enrichment on detail. Budget for that** |
| USGS ShakeMap | Modelled MMI/PGA/PGV grid | Via `properties.products.shakemap` |
| USGS DYFI | Crowdsourced felt intensity within minutes | Via `properties.products.dyfi` |
| `properties.tsunami` | **A flag, not a forecast.** Set when the event meets regional tsunami warning centre notification criteria (typically M≥7.0, shallow, offshore) | Do not treat as a tsunami severity signal |
| `properties.sig` | USGS significance score, computed from magnitude, felt reports and impact | Present in summary feed; a cheap pre-existing composite worth comparing against |
| EMSC | Often faster than USGS for Euro-Mediterranean; app-based felt reports | Not re-verified |
| GEM | Global exposure and vulnerability models, building typologies | Not re-verified |
| NASA ARIA | Damage Proxy Maps, coherence-based, days to weeks | Not re-verified |

### 5.3 Wildfire

| Source | What it gives | Status |
|---|---|---|
| NASA FIRMS | VIIRS 375 m and MODIS 1 km active fire, NRT, API | Not re-verified this round; was live in prior project work |
| NOAA GOES-16/18 | Geostationary fire detection at 5–15 min cadence, coarser | Not re-verified |
| NIFC WFIGS | US incident locations and perimeters, ArcGIS REST | Already used in the existing wildfire dashboard project |
| IRWIN | US inter-agency incident reporting backbone | Not re-verified |
| InciWeb / CAL FIRE | US incident narrative and status; California structured feed | Not re-verified |
| EFFIS / GWIS | European and global burnt area and fire danger | Not re-verified |
| NWS Red Flag Warnings | Forward-looking fire weather risk | Available via NWS CAP/API |
| Digital Atlas of Australia | **Near-real-time bushfire perimeters — the source Aon's AER actually uses** | New this round, not verified |

### 5.4 Wind — rebuilt this round

The single most important correction: **"wind" is not one peril and the industry does
not treat it as one.** Aon's own AER product line splits it into US Hurricane, Japan
Typhoon, Australia Cyclone, European Windstorm, European Hail and US Severe Convective
Storm — six products, different data, different lead times, different customers. Hail
is separated from SCS in Europe and bundled into it in the US.

**Tropical cyclone**

| Source | What it gives | Status |
|---|---|---|
| NHC | Atlantic/E Pacific advisories, forecast cone, wind radii, wind speed probabilities, storm surge | **Live and well structured.** GIS products in shapefile and KML/KMZ. **An RSS feed at nhc.noaa.gov/gis/rss.php with predictable GUIDs** (`gis-120h1wsp64-kml-yyyymmddhhmm` etc.) — a clean polling target. Wind speed probabilities at 34/50/64 kt thresholds, cumulative 0–120 h in 12 h steps, updated every 6 hours with each advisory package. Probabilistic storm surge available only while US watches/warnings are in effect |
| NDFD | Wind speed probability grids, GRIB2 | CONUS-only for the tkdegrib route; international coverage is coarser |
| JTWC | W Pacific and Indian Ocean | **Not verified. Priority gap** — US DoD data availability in this area has changed in recent years and needs checking before being relied on |
| IBTrACS | Historical best-track archive | Not re-verified. The backtesting source |
| GDACS TC module | Already-computed wind and surge impact score | Live via GDACS |

**European windstorm**

| Source | What it gives | Status |
|---|---|---|
| MeteoAlarm | Aggregated official warnings, 38 NMSs, CAP | Live, plus the new API portal (see 5.1) |
| National met services | DWD, Met Office, Météo-France etc. issue the underlying warnings | Not verified individually |
| Named storm lists | Met Office/Met Éireann/KNMI western group and others | MeteoAlarm's RODEO work includes a Storm Name API — useful for event identity across borders, which is a real problem for European windstorm |
| ECMWF / GFS | Raw forecast model output | Not re-verified. Heavyweight |

**Severe convective storm**

| Source | What it gives | Status |
|---|---|---|
| NOAA SPC | Convective outlooks, tornado/hail/wind storm reports | Not re-verified this round |
| NWS API / CAP | Watches and warnings by polygon | Not re-verified |
| **ESWD** | European severe convective storm reports | **DOWNGRADE. Effectively unusable for this project.** The User's Agreement **prohibits commercial use** and requires a signed agreement returned to ESSL. Separately, as of June 2026 ESSL had **temporarily disabled public access to older data** in response to abuse. Round 1 listed this without caveat; that was wrong |

**Gap acknowledged:** GDACS has no severe convective storm hazard type at all. Any
GDACS-anchored monitoring layer is structurally blind to the peril responsible for over
USD 50bn of annual insured loss. This is not a small omission — it is arguably the
strongest single argument for the whole project.

### 5.5 Exposure and vulnerability

Covered in depth in NatCat_Data_Reliability_Reference.md. That document's failure-mode
analysis applies directly and should be treated as the QC standard here.

- Population: WorldPop, LandScan (ambient vs residential distinction matters
  operationally), GHS-POP (what GDACS itself uses), GPW
- Buildings: Microsoft ML footprints, Google Open Buildings, Overture, OSM,
  GlobalBuildingAtlas, national cadastral
- Roads and critical infrastructure: OSM, with the documented
  completeness-versus-governance correlation; GDACS per-event critical infrastructure
  list
- Economic proxies: VIIRS night-lights, gridded GDP
- Vulnerability and coping capacity: INFORM Risk Index, HDI
- **Insurance penetration: no open gridded product exists.** Swiss Re sigma gives
  regional and national figures annually in PDF. This is the weakest link in any
  commercial re-weighting and must be stated as such

---

## 6. Project proposals

### Proposal A — Multi-hazard triage and prioritisation engine

Ingest live feeds across chosen perils, compute an exposure-weighted commercial
severity score, maintain a ranked work queue resolving severity against an SLA clock,
deploy as a dashboard.

Pros: closest replica of the job; exercises the core prioritisation scenario directly; reuses the
React/FastAPI/Postgres stack; live demonstrable artefact.
Cons: largest scope; risks becoming an engineering project rather than an analytical
one; the SLA layer requires unvalidatable assumptions; **and see section 9, tension 5 —
the base rates mean a live dashboard will be empty most of the time.**

### Proposal B — Divergence analysis: humanitarian vs commercial triage

Retrospective. Take N historical events, compute both a GDACS/PAGER-style humanitarian
score and an insurance-weighted score, quantify where and why they diverge.

Pros: purely analytical, defensible, no deployment burden; produces a written argument;
directly demonstrates independent judgment. **Round 2 strengthens this considerably —
there are now concrete, sourced worked examples (section 4.5) and a published industry
decision rule to validate against (PCS thresholds, section 4.1).**
Cons: less visually impressive; no live-operations feel; needs careful event sampling to
avoid cherry-picking.

### Proposal C — Verification and QC layer

Replicate the *verification* step. Given an automated alert and a candidate
deliverable, apply structured QC against the failure modes in
NatCat_Data_Reliability_Reference.md and document what was caught.

Pros: targets a responsibility named repeatedly in the listings that almost no
portfolio project demonstrates; small scope; MIS's public human-verification step
(section 4.3) is direct industry precedent.
Cons: hardest to make legible as a portfolio piece; no obvious visual output.

### Proposal D — Shift handover / queue-state model (NEW)

Not a full alternative — a component that could attach to A or C. Model the work queue
as shared state that survives a follow-the-sun handover: what is in flight, what is
blocked on data, what was deprioritised and why, what the next shift must decide.

Pros: nobody does this; it is real (section 1.1); it generates operational-judgment
scenarios directly; it is small.
Cons: only legible to someone who knows the domain; hard to explain in a CV line.

### Note on combination

B is the analytical justification for the scoring logic A implements. C and D could be
components of A rather than separate builds. A plausible shape remains B first, then A
built on its findings.

---

## 7. Open questions — since resolved in the plan

1. **Sequencing against imagery (SAR) work.** Resolved: this project runs first;
   imagery work stays separate.
2. **Which proposal.** Resolved: A is built, with B's divergence reasoning behind its
   scoring and C's QC thinking in the building-footprint drill-down. D (handover) was
   dropped as out of scope.
3. **Scope of perils.** Resolved: earthquake, tropical cyclone wind and wildfire, US
   only. Flood excluded.
4. **Which wind sub-peril.** Resolved: tropical cyclone (NHC).
5. **Deployment.** Resolved: deployed live app (plan D14), with the base-rate problem
   handled by accepting a quiet queue (plan D2; see also open decision O15).

---

## 8. Stated assumptions and genuine unknowns

Recorded so they are never silently guessed:

- Commercial providers' actual SLA durations. Unknown. Copernicus EMS SL1 (2–12 h after
  image reception) is the nearest public analogue and should be used as a **declared
  proxy**, not presented as any provider's figure
- Where a provider's SLA clock starts — event onset, tasking, or image reception. Unknown
- How a provider weights contractual obligation against event severity. Unknown
- Customer contract structure and whether SLAs are per-customer or per-product. Unknown
- Whether providers use interferometric coherence for earthquake products. Inferred from
  pre-imaging language, not stated. Must not be asserted
- Live parametric trigger locations and thresholds. Not publicly available in usable
  form
- Insurance penetration as a gridded surface. Does not exist openly
- Whether social media monitoring is currently feasible under platform API terms.
  Not investigated

---

## 9. Tensions and problems flagged

Recorded rather than smoothed over.

**Tension 1 — the "original contribution" framing is weaker than round 1 implied.**
Round 1 positioned a commercially re-weighted triage score as original analysis. Round
2 shows the industry already publishes a designation rule with region-varying
thresholds (PCS) and already runs automated commercial event response consuming
commercial SAR data (Aon AER). Two available framings, to be picked deliberately:
(a) *"I invented a commercial triage score"* — weaker, more falsifiable, and invites
the question of why it differs from what Aon does;
(b) *"I reconstructed the logic the industry actually uses from published sources, and
quantified where open humanitarian feeds fail to capture it"* — more defensible, better
grounded, and demonstrates research judgment rather than invention.
(b) looks stronger, but it is a positioning decision, not a technical one.

**Tension 2 — the real triage input is private and cannot be replicated.** Aon's AER
computes loss on the client's own portfolio; commercial wildfire products report exposed
limit against client exposure. Actual triage is driven by exposure *to that specific
customer*. Every open proxy — GDP, night lights, GHS-POP, national insurance
penetration — is a coarse stand-in. This bounds how good the project can be. Better
stated up front as a limitation than discovered by a reader.

**Tension 3 — the SLA clock probably does not start where an intuitive model would put
it.** See 2.1. Modelling from event onset conflates satellite revisit with analyst
performance.

**Tension 4 — 24/7 is follow-the-sun, so the queue is handover state, not a private
ranking.** See 1.1.

**Tension 5 — base rates make a live dashboard mostly empty, and this cuts against
Proposal A as a demonstrable artefact.** PAGER: ~1.5 orange-or-above earthquakes per
year. Commercial SAR flood analysis: tens of events a year globally. Swiss
Re: 190 nat cat events worldwide in 2025, of which a handful were commercially major.
A live dashboard opened on an arbitrary Tuesday will show nothing worth triaging. Any
demonstrable version needs either a historical replay mode, a synthetic scenario
injector, or acceptance that the artefact is usually idle. This is a real design
constraint, not a detail, and it should be decided before anything is built.

**Tension 6 — ESWD is not usable.** Commercial use prohibited, signed agreement
required, historical public access disabled as of June 2026. Round 1 listed it
uncaveated.

**Tension 7 — "wind" is a category error, and the peril set may be the wrong axis
entirely.** The industry splits wind six ways by region and sub-peril. More importantly,
GDACS has no severe convective storm category at all, while SCS has produced over USD
50bn of insured loss annually for three years. That suggests the interesting question
is not "which perils do I cover" but "**which commercially significant perils are
invisible to the public humanitarian monitoring stack**" — a different and sharper
project framing. Worth considering before answering question 3.

**Tension 8 — an app does not demonstrate judgment; the reasoning behind it does.** The
skill to demonstrate is independent judgment under ambiguity, not technical
output. A dashboard demonstrates engineering. A defended position on what should be
prioritised and why demonstrates judgment. Whatever is built, the
written argument is the deliverable and the code is the evidence, not the reverse.

---

## 10. Progress log

**2026-08-21** — Research round 1. Role analysed from published listings; SAR confirmed
peripheral. Contractual-vs-severity partially resolved. GDACS and PAGER documented.
Three proposals drafted, none decided. Data catalogue compiled, unverified.

**2026-08-22** — Research round 2, focused on the customer side and on verification.
Added: PCS designation gate and its region-varying thresholds; Aon Impact Forecasting
AER timelines and peril split, including confirmation that a commercial SAR provider supplies AER's Global
Flood and US Wildfire products; McKenzie Intelligence Services and the FNOI/FNOL
framing, plus Verisk's July 2026 acquisition of MIS; parametric trigger taxonomy and
the trigger-proximity idea; Swiss Re sigma 1/2026 regional insured-versus-economic
figures and six worked divergence examples, of which Myanmar/Thailand is the strongest;
Copernicus EMS published service levels and the image-reception clock start; GDACS and
USGS API field-level structure including the two-tier PAGER fetch cost; MeteoAlarm's
new API portal; ESWD downgraded to unusable; wind section rebuilt around six industry
sub-perils; follow-the-sun handover identified from the US job listing. Eight tensions
recorded in section 9. Proposal D added. Nothing decided at this point; every open question was subsequently resolved in
NATCAT_TRIAGE_PROJECT_PLAN.md.
