# backend/app/nifc.py

from datetime import datetime, timezone
from typing import Any

import httpx
from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import nsi, scoring
from .models import Event, RawNifcEvent

# Endpoint re-verified 2026-08-25 (previously verified by WildfireDashboard
# 2026-07-28, and again in this project's Phase 0). NIFC restructures these
# URLs periodically - if ingestion starts failing, re-verify against
# https://data-nifc.opendata.arcgis.com/datasets/nifc::wfigs-current-interagency-fire-perimeters
# before assuming a code bug.
QUERY_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Interagency_Perimeters_Current/FeatureServer/0/query"
)

OUT_FIELDS = (
    "attr_IrwinID,attr_IncidentName,poly_GISAcres,attr_IncidentSize,"
    "attr_FireDiscoveryDateTime,poly_DateCurrent,attr_PercentContained,"
    "attr_FireCause,attr_IncidentComplexityLevel,attr_POOState"
)


def _parse_epoch_ms(value: Any) -> datetime | None:
    """WFIGS date fields come back as epoch milliseconds even under
    f=geojson."""
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def fetch_perimeters() -> list[dict]:
    """Fetch current wildfire perimeters. No geographic filtering needed -
    WFIGS is inherently a US interagency system, unlike USGS's global feed
    (plan D3 is automatically satisfied here, not something this ingest
    has to enforce itself)."""
    params = {"where": "1=1", "outFields": OUT_FIELDS, "f": "geojson"}
    resp = httpx.get(QUERY_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()["features"]


def parse_feature(feature: dict) -> dict[str, Any]:
    props = feature["properties"]
    return {
        "id": props.get("attr_IrwinID"),
        "incident_name": props.get("attr_IncidentName"),
        "gis_acres": props.get("poly_GISAcres"),
        "incident_size": props.get("attr_IncidentSize"),
        "discovery_time": _parse_epoch_ms(props.get("attr_FireDiscoveryDateTime")),
        "date_current": _parse_epoch_ms(props.get("poly_DateCurrent")),
        "percent_contained": props.get("attr_PercentContained"),
        "fire_cause": props.get("attr_FireCause"),
        "complexity_level": props.get("attr_IncidentComplexityLevel"),
        "poo_state": props.get("attr_POOState"),
        "geometry": feature.get("geometry"),
        "raw_properties": props,
    }


def upsert_events(session: Session, features: list[dict]) -> dict[str, int]:
    """Parse and upsert features into raw_nifc_events. A feature with no
    IRWIN ID can't be keyed or traced back to anything - skipped rather
    than guessing an id, and counted so a systematic upstream problem
    would be visible rather than silently dropped."""
    now = datetime.now(timezone.utc)
    fetched = 0
    skipped_no_id = 0

    for feature in features:
        fields = parse_feature(feature)
        if not fields["id"]:
            skipped_no_id += 1
            continue

        existing = session.get(RawNifcEvent, fields["id"])
        fields["last_polled_at"] = now
        fields["first_seen_at"] = existing.first_seen_at if existing else now

        session.merge(RawNifcEvent(**fields))
        fetched += 1

    session.commit()
    return {"fetched": fetched, "skipped_no_id": skipped_no_id}


def normalize_to_events(session: Session) -> int:
    """Normalise every row in raw_nifc_events into the unified events
    table. Unlike earthquake, wildfire gives a real footprint polygon from
    day one - centroid computed via shapely for the point
    longitude/latitude, the full polygon stored in footprint_geojson
    rather than left null."""
    now = datetime.now(timezone.utc)
    raw_rows = session.execute(select(RawNifcEvent)).scalars().all()
    normalized = 0

    for raw in raw_rows:
        existing = session.get(Event, ("nifc", raw.id))

        centroid_lon, centroid_lat = None, None
        if raw.geometry:
            try:
                centroid = shape(raw.geometry).centroid
                centroid_lon, centroid_lat = centroid.x, centroid.y
            except Exception:
                pass  # malformed geometry shouldn't take the whole ingest down

        event = Event(
            source="nifc",
            source_event_id=raw.id,
            peril="wildfire",
            name=raw.incident_name,
            event_time=raw.discovery_time or raw.date_current or now,
            last_updated=raw.date_current,
            longitude=centroid_lon,
            latitude=centroid_lat,
            footprint_geojson=raw.geometry,
            primary_metric_label="acres_burned",
            primary_metric_value=raw.gis_acres,
            # No published humanitarian/commercial alert baseline for
            # wildfire the way PAGER exists for earthquake (plan 5.4) -
            # left null rather than approximated.
            source_alert_level=None,
            # Scoring is expensive-tier (NSI intersection) and runs
            # separately via score_events(), not on every normalisation
            # pass - preserve whatever's already there rather than
            # wiping it back to null on every poll.
            humanitarian_score=existing.humanitarian_score if existing else None,
            economic_score=existing.economic_score if existing else None,
            overall_score=existing.overall_score if existing else None,
            confidence=existing.confidence if existing else "not yet scored",
            scored_at=existing.scored_at if existing else None,
            first_seen_at=existing.first_seen_at if existing else now,
            last_synced_at=now,
        )
        session.merge(event)
        normalized += 1

    session.commit()
    return normalized


def score_events(session: Session, limit: int = 20) -> dict[str, int]:
    """Expensive-tier scoring (NSI point-in-polygon intersection) for
    wildfire events, run separately from normalisation and guarded on two
    fronts: only (re)scores an event if it's never been scored, or its
    perimeter has genuinely changed since the last time it was scored
    (last_updated newer than scored_at) - running NSI intersection for all
    ~200+ wildfires on every poll would be far too slow (a single NSI bbox
    query took ~30s in Phase 0 testing). `limit` caps how many get scored
    per call so a single poll stays bounded; events not reached this call
    get picked up on a later one."""
    now = datetime.now(timezone.utc)
    candidates = (
        session.execute(select(Event).where(Event.peril == "wildfire")).scalars().all()
    )
    needs_scoring = [
        e
        for e in candidates
        if e.scored_at is None or (e.last_updated is not None and e.last_updated > e.scored_at)
    ]

    scored = 0
    failed = 0
    for event in needs_scoring[:limit]:
        try:
            exposure = nsi.summarize_exposure(event.footprint_geojson)
        except httpx.HTTPError:
            failed += 1
            continue

        event.humanitarian_score = scoring.humanitarian_score(exposure["population_exposed"])
        event.economic_score = scoring.economic_score(exposure["replacement_cost_usd"])
        event.overall_score = scoring.overall_score(event.humanitarian_score, event.economic_score)
        event.confidence = (
            f"NSI intersection, {exposure['structure_count']} structures found"
            if exposure["structure_count"] is not None
            else "no footprint available"
        )
        event.scored_at = now
        scored += 1

    session.commit()
    return {"scored": scored, "failed": failed, "remaining": max(0, len(needs_scoring) - scored)}
