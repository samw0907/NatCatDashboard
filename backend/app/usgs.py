# backend/app/usgs.py

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from shapely.geometry import Polygon, mapping
from shapely.ops import unary_union
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import nsi, scoring
from .models import Event, RawUsgsEvent

QUERY_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# US bounding box - covers CONUS, Alaska (most of it) and Hawaii. Known gap:
# the westernmost Aleutian Islands cross the antimeridian and fall outside
# this box. Accepted as a Phase 1 simplification - revisit if it matters.
US_BBOX = {"minlatitude": 15, "maxlatitude": 72, "minlongitude": -180, "maxlongitude": -60}

MIN_MAGNITUDE = 2.5


def _parse_epoch_ms(value: int | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def fetch_summary(days: int = 14) -> list[dict]:
    """Fetch raw earthquake features for the US bounding box over the last
    `days` days. Uses the query endpoint rather than a pre-built summary
    feed, since scoping to the US (plan D3) needs geographic filtering the
    pre-built feeds don't offer. The geographic + magnitude filter keeps the
    request small - this isn't the unfiltered-global-catalog case USGS's
    routine-polling advice is warning against."""
    starttime = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    params = {
        "format": "geojson",
        "starttime": starttime,
        "minmagnitude": MIN_MAGNITUDE,
        "eventtype": "earthquake",
        **US_BBOX,
    }
    resp = httpx.get(QUERY_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()["features"]


MIN_FOOTPRINT_MMI = 4.0


def _mmi_contour_polygon(cont_mmi_geojson: dict, min_mmi: float) -> dict | None:
    """Builds a polygon for "shaking at or above min_mmi" from ShakeMap's
    MMI contour lines. Real contour output is messier than it looks:
    fragments aren't reliably closed rings (checked live - roughly 2/3 of
    fragments closed on a real M7.4 event, the rest open pieces clipped at
    the computation grid's edge). Only closed rings are used, unioned
    together - a defensible simplification (slightly conservative at grid
    edges), not a perfect reconstruction. Uses the lowest available
    contour level at or above min_mmi, since ShakeMap doesn't always
    compute every 0.5-step level for every event."""
    candidates = [
        f
        for f in cont_mmi_geojson.get("features", [])
        if f.get("properties", {}).get("value") is not None
        and f["properties"]["value"] >= min_mmi
    ]
    if not candidates:
        return None
    target_value = min(f["properties"]["value"] for f in candidates)

    rings = []
    for f in candidates:
        if f["properties"]["value"] != target_value:
            continue
        for line in f["geometry"]["coordinates"]:
            if len(line) >= 4 and line[0] == line[-1]:
                rings.append(Polygon(line).buffer(0))
    if not rings:
        return None
    return mapping(unary_union(rings))


def fetch_enrichment(detail_url: str) -> dict[str, Any]:
    """Two-tier fetch: given an event's detail feed URL, fetch the
    losspager product's exposure/loss data and the ShakeMap MMI contour in
    one pass (both need the same detail_url fetch, no point doing it
    twice). Any field stays None if that product doesn't exist for this
    event - a missing shakemap doesn't block losspager data or vice versa."""
    resp = httpx.get(detail_url, timeout=30)
    resp.raise_for_status()
    detail = resp.json()
    products = detail.get("properties", {}).get("products", {})

    result: dict[str, Any] = {
        "population_exposure": None,
        "total_fatalities": None,
        "total_economic_loss_usd": None,
        "mmi_contour_geojson": None,
    }

    losspager = products.get("losspager")
    if losspager:
        contents = losspager[0].get("contents", {})
        exposures_url = contents.get("json/exposures.json", {}).get("url")
        losses_url = contents.get("json/losses.json", {}).get("url")
        if exposures_url and losses_url:
            exposures = httpx.get(exposures_url, timeout=30).json()
            losses = httpx.get(losses_url, timeout=30).json()
            result["population_exposure"] = exposures.get("population_exposure")
            result["total_fatalities"] = losses.get("empirical_fatality", {}).get("total_fatalities")
            result["total_economic_loss_usd"] = losses.get("empirical_economic", {}).get("total_dollars")

    shakemap = products.get("shakemap")
    if shakemap:
        contents = shakemap[0].get("contents", {})
        cont_url = contents.get("download/cont_mmi.json", {}).get("url")
        if cont_url:
            cont_geojson = httpx.get(cont_url, timeout=30).json()
            result["mmi_contour_geojson"] = _mmi_contour_polygon(cont_geojson, MIN_FOOTPRINT_MMI)

    return result


def parse_feature(feature: dict) -> dict[str, Any]:
    """Map one USGS GeoJSON feature to RawUsgsEvent column values."""
    props = feature["properties"]
    coords = feature["geometry"]["coordinates"]  # [lon, lat, depth_km]
    return {
        "id": feature["id"],
        "mag": props.get("mag"),
        "place": props.get("place"),
        "event_time": _parse_epoch_ms(props.get("time")),
        "updated": _parse_epoch_ms(props.get("updated")),
        "felt": props.get("felt"),
        "cdi": props.get("cdi"),
        "mmi": props.get("mmi"),
        "alert": props.get("alert"),
        "sig": props.get("sig"),
        "tsunami": bool(props.get("tsunami")),
        "event_type": props.get("type"),
        "title": props.get("title"),
        "url": props.get("url"),
        "detail_url": props.get("detail"),
        "longitude": coords[0] if len(coords) > 0 else None,
        "latitude": coords[1] if len(coords) > 1 else None,
        "depth_km": coords[2] if len(coords) > 2 else None,
        "raw_properties": props,
    }


def upsert_events(session: Session, features: list[dict]) -> dict[str, int]:
    """Parse and upsert features into raw_usgs_events. Fetches PAGER
    enrichment only for events with a non-null `alert` - PAGER's own team
    has already decided which events warrant a losspager product, so that's
    the screening threshold (O3) rather than an invented magnitude cutoff.
    A failed or skipped enrichment fetch never overwrites enrichment data
    already stored from a previous poll."""
    now = datetime.now(timezone.utc)
    fetched = 0
    enriched = 0
    enrichment_failed = 0

    for feature in features:
        fields = parse_feature(feature)
        existing = session.get(RawUsgsEvent, fields["id"])

        enrichment_fields = {
            "pager_population_exposure": existing.pager_population_exposure if existing else None,
            "pager_total_fatalities": existing.pager_total_fatalities if existing else None,
            "pager_total_economic_loss_usd": existing.pager_total_economic_loss_usd if existing else None,
            "mmi_contour_geojson": existing.mmi_contour_geojson if existing else None,
            "enrichment_fetched_at": existing.enrichment_fetched_at if existing else None,
        }
        if fields["alert"] is not None and fields["detail_url"]:
            try:
                enrichment = fetch_enrichment(fields["detail_url"])
            except httpx.HTTPError:
                enrichment = None
                enrichment_failed += 1
            if enrichment:
                enrichment_fields = {
                    "pager_population_exposure": enrichment["population_exposure"],
                    "pager_total_fatalities": enrichment["total_fatalities"],
                    "pager_total_economic_loss_usd": enrichment["total_economic_loss_usd"],
                    "mmi_contour_geojson": enrichment["mmi_contour_geojson"],
                    "enrichment_fetched_at": now,
                }
                enriched += 1
        fields.update(enrichment_fields)

        fields["last_polled_at"] = now
        fields["first_seen_at"] = existing.first_seen_at if existing else now

        session.merge(RawUsgsEvent(**fields))
        fetched += 1

    session.commit()
    return {"fetched": fetched, "enriched": enriched, "enrichment_failed": enrichment_failed}


def _weighted_population_exposure(pager_population_exposure: dict | None) -> float | None:
    """Sums PAGER's MMI-banded population exposure, weighted by intensity
    (plan section 6.3: "weighted by hazard intensity where the source
    provides it"). Only counts MMI 4+ ("Light" and above on the Modified
    Mercalli scale, where shaking becomes widely felt and minor damage
    becomes possible) - MMI 1-3 is negligible/unfelt shaking, and including
    it would inflate the count with people who experienced no meaningful
    risk. Weight is (mmi - 3), so MMI 4 counts once per capita and MMI 10
    counts seven times - a simple, transparent increasing weighting, not a
    physically-derived damage curve; stated as the simplification it is."""
    if not pager_population_exposure:
        return None
    mmi_values = pager_population_exposure.get("mmi", [])
    exposure_values = pager_population_exposure.get("aggregated_exposure", [])
    total = sum(pop * (mmi - 3) for mmi, pop in zip(mmi_values, exposure_values) if mmi >= 4)
    return total if total > 0 else None


def _score_earthquake_humanitarian(raw: RawUsgsEvent) -> tuple[float | None, str]:
    """Cheap pass, runs on every normalisation: PAGER's own MMI-banded
    population exposure, weighted by intensity, fed through the shared
    continuous log-scale score (scoring.py, O4 resolved 2026-08-25).
    Economic axis is scored separately by score_economic() (expensive-tier,
    NSI-based, guarded) - not computed here. Only covers the minority of
    events with a losspager product."""
    if raw.alert is None:
        return None, "no PAGER product available"

    exposure = _weighted_population_exposure(raw.pager_population_exposure)
    humanitarian = scoring.humanitarian_score(exposure)
    if humanitarian is None:
        return None, "PAGER product present but no usable population exposure data"
    if raw.mmi_contour_geojson:
        return humanitarian, "humanitarian axis scored; economic axis pending"
    return humanitarian, "humanitarian axis scored; no footprint geometry available for the economic axis"


def normalize_to_events(session: Session) -> int:
    """Normalise every row currently in raw_usgs_events into the unified
    events table (plan section 8.1, ingest step 3). Reads the whole raw
    table rather than just newly-touched rows - the raw table is small
    (rolling ~14-day window) so this is cheap, and it keeps normalisation
    idempotent and simple rather than needing to track what changed."""
    now = datetime.now(timezone.utc)
    raw_rows = session.execute(select(RawUsgsEvent)).scalars().all()
    normalized = 0

    for raw in raw_rows:
        existing = session.get(Event, ("usgs", raw.id))
        humanitarian_score, humanitarian_confidence = _score_earthquake_humanitarian(raw)

        # Economic score and scored_at are owned by the separate expensive
        # pass (score_economic()) - preserved here, not recomputed. Once
        # that pass has actually run (scored_at set), its confidence
        # message is the authoritative one; otherwise use the cheap pass's.
        economic_score = existing.economic_score if existing else None
        scored_at = existing.scored_at if existing else None
        confidence = (
            existing.confidence if (existing and existing.scored_at) else humanitarian_confidence
        )

        event = Event(
            source="usgs",
            source_event_id=raw.id,
            peril="earthquake",
            name=raw.title or raw.place,
            event_time=raw.event_time,
            last_updated=raw.updated,
            longitude=raw.longitude,
            latitude=raw.latitude,
            # Real MMI contour polygon where a shakemap product exists
            # (see fetch_enrichment/_mmi_contour_polygon above) - null
            # otherwise, never approximated with an invented radius.
            footprint_geojson=raw.mmi_contour_geojson,
            primary_metric_label="magnitude",
            primary_metric_value=raw.mag,
            source_alert_level=raw.alert,
            humanitarian_score=humanitarian_score,
            economic_score=economic_score,
            overall_score=scoring.overall_score(humanitarian_score, economic_score),
            confidence=confidence,
            scored_at=scored_at,
            first_seen_at=existing.first_seen_at if existing else now,
            last_synced_at=now,
        )
        session.merge(event)
        normalized += 1

    session.commit()
    return normalized


def score_economic(session: Session, limit: int = 20) -> dict[str, int]:
    """Expensive-tier: NSI point-in-polygon intersection against the MMI
    contour footprint for earthquake's economic axis. Kept separate from
    normalisation and guarded the same way as wildfire's score_events() -
    only (re)scores an event that's never been scored or whose footprint
    changed since it last was. Humanitarian score is untouched here - it's
    already set from PAGER's own exposure data (cheap pass) and NSI's
    population figure would be a worse substitute for it, not an
    improvement, so this only ever writes economic_score, overall_score,
    confidence and scored_at."""
    now = datetime.now(timezone.utc)
    # footprint_geojson filtered in Python, not SQL - a JSON column holding
    # Python None gets stored as the JSON *value* null by default in
    # SQLAlchemy, not SQL NULL, so `.is_not(None)` at the query level
    # matches every row regardless of whether it has real geometry (caught
    # live, 2026-08-26: it silently treated all ~400 earthquakes as
    # candidates instead of the ~4 with an actual contour). Matches
    # nifc.py's score_events(), which never had this bug because it never
    # filtered on footprint_geojson at the SQL level to begin with.
    candidates = session.execute(select(Event).where(Event.peril == "earthquake")).scalars().all()
    needs_scoring = [
        e
        for e in candidates
        if e.footprint_geojson
        and (e.scored_at is None or (e.last_updated is not None and e.last_updated > e.scored_at))
    ]

    scored = 0
    failed = 0
    for event in needs_scoring[:limit]:
        try:
            exposure = nsi.summarize_exposure(event.footprint_geojson)
        except httpx.HTTPError:
            failed += 1
            continue

        event.economic_score = scoring.economic_score(exposure["replacement_cost_usd"])
        event.overall_score = scoring.overall_score(event.humanitarian_score, event.economic_score)
        event.confidence = (
            f"humanitarian: PAGER exposure. economic: NSI intersection, "
            f"{exposure['structure_count']} structures found"
        )
        event.scored_at = now
        scored += 1

    session.commit()
    return {"scored": scored, "failed": failed, "remaining": max(0, len(needs_scoring) - scored)}
