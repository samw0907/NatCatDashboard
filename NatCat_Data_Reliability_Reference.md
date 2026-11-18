# NatCat Data Reliability — Common Data Types and Their Failure Modes

Building footprints are covered in the project plan (section 7: OSM vs Microsoft/Google
ML-derived footprints, and the false-positive/coverage-gap distinction). This extends
the same discipline to the other data types that come up constantly in rapid NatCat
analysis. Every claim below is sourced, not assumed.

---

## Population / exposure data

**The main products**: WorldPop, LandScan (Global and HD), GHS-POP, GPW (Gridded
Population of the World), GRUMP. None of these are census data directly — all are
*modelled* surfaces that redistribute coarser official statistics (province/district
totals) down to a fine grid, using proxies like night-lights, land cover, and building
density.

**Ambient vs residential population — the single most operationally important
distinction.** LandScan explicitly models *ambient* population — where people actually
are throughout an average day, accounting for work and travel patterns. WorldPop
primarily models *residential* population — where people are registered/sleep. A
wildfire or flood hitting a business district at 2pm has a completely different real
exposure than the same area at 2am, and using a residential-population dataset for a
daytime event (or vice versa) can materially misstate who's actually exposed. This is
worth stating explicitly whenever population data is used — which product you reach for
should depend on time-of-day relative to the event, not just "which one's most
accurate."

**Accuracy is regional, not universal — same pattern as building footprints.**
Different studies crown different "winners": WorldPop performed best in a China
comparison; LandScan performed best across mainland Southeast Asia; results were mixed
across Myanmar, Laos, and Cambodia in the same study. There's no single "most accurate"
population product — it depends on the specific country's data ecosystem.

**Real, documented failure case worth knowing**: a Sweden-specific validation study
found both WorldPop and GHS-POP *consistently overestimated* population exposed to
flooding, contradicting the common assumption that these datasets tend to
under-count. Overestimation bias is just as real a risk as underestimation.

**Temporal interpolation is a hidden methodology gap.** WorldPop's most detailed
modelling is only actually re-run for specific census-anchored years (2010, 2015,
2020); every other year is linearly interpolated between them, which the dataset's own
documentation acknowledges may produce unrealistic results at the individual grid-cell
level. If working with any year other than one of those anchor years, that number is
an estimate built on an estimate, not independently modelled.

**A direct quote worth having, since it states the core risk plainly**: LandScan's own
2025 methodology paper states that traditional population modelling approaches often
overlook inherent uncertainties in the estimation process, which can create a false
sense of certainty in population estimates, potentially leading to flawed decisions.
That's the dataset's own creators warning against treating a precise-looking number as
more reliable than it is.

---

## Elevation / DEM data

**The default global product is SRTM** (Shuttle Radar Topography Mission), and it
underpins RTC/orthorectification in most SAR processing pipelines — worth knowing its
limitations precisely, since they propagate directly into anything built on top of it.

**Age**: the data was collected in February 2000 — a single 11-day mission, never
repeated globally at that resolution. Anything built or changed since then (new
construction, mining, erosion, landslide-altered terrain) isn't reflected. A DEM used
for orthorectifying a scene over an area that's been built up in the 25 years since
won't correctly represent current ground elevation there.

**Voids — and how unevenly they're distributed.** Data gaps affect roughly 3.4 million
individual void areas globally, totalling around 796,000 km². These aren't randomly
scattered — they cluster specifically in water bodies, dense vegetation, and steep or
rugged terrain (via the same layover/shadow mechanism familiar from SAR). The distribution can be extreme: Nepal alone has voids covering roughly
9.6% of its total land area. Void-filling (interpolation) is applied to produce a
"complete" public product, but the fill itself is measurably less accurate than the
real radar-derived data around it — one validation study found filled areas in complex
dune terrain reached 14m RMSE versus 1.3-5.2m for genuine data in well-behaved terrain.

**Vegetation penetration — directly relevant to SAR RTC and flood work.** SRTM's
C-band radar partially penetrates vegetation canopy, meaning the recorded "elevation"
in forested areas sits somewhere between true bare ground and canopy top, not a clean
ground surface. Since RTC terrain-flattening depends on the DEM accurately representing
the actual ground, this introduces a systematic bias in exactly the kind of vegetated
terrain that already causes double-bounce ambiguity in flood detection — two separate
sources of uncertainty compounding in the same problem areas.

**Accuracy varies by terrain, not a flat number.** Validated RMSE in stable desert
terrain sits around 1.3-5.2m; accuracy degrades meaningfully in mountainous or
structurally complex terrain. Any accuracy figure quoted for a DEM is a global average,
not a guarantee for a specific AOI.

---

## Roads / critical infrastructure data

**OSM is the default open source here too, with the same completeness pattern as
buildings.** A widely-cited study found OSM captures roughly 83% of the world's roads
globally, but with meaningfully larger gaps specifically in countries with weaker
governance and lower internet penetration — the completeness gap correlates with the
same socioeconomic factors that predict disaster vulnerability in the first place, which
is precisely the wrong correlation for operational reliance.

**Directly disaster-relevant, not just theoretical**: relief agencies used OSM road
data operationally during Hurricane Dorian in the Bahamas to understand which houses,
schools, and clinics were reachable. Tools like Kontur's "Disaster Ninja" explicitly
cross-reference road completeness against population density specifically to flag
densely-populated areas with poor road mapping as elevated-risk zones for response
planning — the gap in the data becomes an operational risk factor in its own right, not
just an analytical inconvenience.

**Completeness changes fast and unevenly over time.** Iran's OSM road network grew from
4,300 km in 2008 to 489,400 km by 2016 — over 100x in eight years. Whatever the
completeness picture was even two or three years ago for a given region may not hold
today; this isn't a static property of a place.

---

## The pattern underneath all four

Every one of these data types shares the same underlying shape of risk, and it's worth
being able to say this as one coherent point rather than four separate facts:

1. **Global reputation doesn't predict regional reliability.** Every product here has
   a global accuracy or completeness figure that sounds authoritative, and every one of
   them varies substantially by country or terrain type underneath that headline
   number — Spain's building footprint gap, Sweden's flood-exposure overestimation,
   Nepal's DEM void concentration, road completeness tracking governance quality. The
   average is real, but it's rarely the number that matters for a specific AOI.
2. **Automated/modelled data and human-curated data fail differently, not just to
   different degrees.** ML-derived building footprints and interpolated population
   grids produce confident-looking wrong answers (a rock becomes a building; an
   interpolated year looks as precise as a modelled one). Human-curated data like
   hand-traced OSM more often just has gaps — it's honestly incomplete rather than
   confidently wrong. Knowing which failure mode a given source is prone to changes
   what you should actually check.
3. **Vintage is a silent limitation in almost all of them.** SRTM from 2000, WorldPop
   interpolated between census years, building/road data reflecting whatever moment
   community mapping happened to capture — none of these datasets are live, and none
   say so loudly on the tin.
4. **The datasets' own creators are increasingly explicit that precision isn't the same
   as reliability** — LandScan's own paper warns against the false sense of certainty
   precise-looking numbers create. That's not a criticism from outside; it's the
   field's own honest self-assessment.

The working discipline that follows: don't trust a number because it's
official-sounding or precise-looking, check it against an independent source, understand
the specific mechanism behind a discrepancy before acting on it, and say plainly what's
still uncertain rather than presenting false confidence.
