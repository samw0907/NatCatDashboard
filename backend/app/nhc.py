# backend/app/nhc.py

import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import httpx
import pyogrio
from shapely.geometry import mapping
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import nsi, scoring
from .models import Event, RawNhcRssItem, RawNhcStorm

CURRENT_STORMS_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"

# https://www.nhc.noaa.gov/gis/rss.php is a documentation/landing page, not
# a feed - confirmed in Phase 0 (2026-08-23). The real per-basin feeds live
# here. Central Pacific included since Phase 0 found active CP storms that
# neither the Atlantic nor East Pacific feed would ever cover.
RSS_BASIN_URLS = {
    "at": "https://www.nhc.noaa.gov/gis-at.xml",
    "ep": "https://www.nhc.noaa.gov/gis-ep.xml",
    "cp": "https://www.nhc.noaa.gov/gis-cp.xml",
}

NHC_XML_NS = "https://www.nhc.noaa.gov"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_rfc822(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = parsedate_to_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# --- CurrentStorms.json ---


def fetch_current_storms() -> list[dict]:
    resp = httpx.get(CURRENT_STORMS_URL, timeout=30)
    resp.raise_for_status()
    return resp.json().get("activeStorms", [])


def fetch_wind_radii_footprint(storm: dict) -> dict | None:
    """Fetch the storm's current wind radii shapefile (initialWindExtent -
    current radii, not the forecast, staying consistent with earthquake/
    wildfire representing current state) and return the polygon for the
    lowest available wind-speed threshold (broadest extent, e.g. 34kt if
    present) as GeoJSON - analogous to earthquake's MMI 4+ threshold.

    Downloaded to a temp file rather than read directly over HTTP via
    GDAL's /vsizip/vsicurl/ virtual filesystem - that combination took 30+
    seconds for a file under 4KB in testing, too slow to be practical for
    what's normally a handful of active storms. A plain download plus a
    local read is fast and reliable.

    Returns None if there's no wind radii product yet (common for a very
    new or very weak system)."""
    zip_url = storm.get("initialWindExtent", {}).get("zipFile")
    if not zip_url:
        return None

    resp = httpx.get(zip_url, timeout=30)
    resp.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        f.write(resp.content)
        temp_path = f.name

    try:
        vsi_path = f"/vsizip/{temp_path}"
        layer_name = next(
            (name for name, geom_type in pyogrio.list_layers(vsi_path) if "initialradii" in name.lower()),
            None,
        )
        if layer_name is None:
            return None
        gdf = gpd.read_file(vsi_path, layer=layer_name)
    finally:
        Path(temp_path).unlink(missing_ok=True)

    if gdf.empty or "RADII" not in gdf.columns:
        return None
    gdf = gdf.sort_values("RADII")
    return mapping(gdf.geometry.iloc[0])


def parse_storm(storm: dict) -> dict[str, Any]:
    return {
        "id": storm["id"],
        "name": storm.get("name"),
        "classification": storm.get("classification"),
        "intensity_kt": _as_float(storm.get("intensity")),
        "pressure_mb": _as_float(storm.get("pressure")),
        "longitude": storm.get("longitudeNumeric"),
        "latitude": storm.get("latitudeNumeric"),
        "movement_dir": _as_float(storm.get("movementDir")),
        "movement_speed_kt": _as_float(storm.get("movementSpeed")),
        "advisory_num": storm.get("publicAdvisory", {}).get("advNum"),
        "last_update": _parse_iso(storm.get("lastUpdate")),
        "raw_properties": storm,
    }


def upsert_storms(session: Session, storms: list[dict]) -> dict[str, int]:
    """Fetches the wind radii footprint for every storm on every poll -
    unlike earthquake/wildfire's volumes, active storm counts are always
    small (typically 0-5 globally), so this doesn't need the same
    cheap-screen/expensive-enrich split; a failed footprint fetch never
    overwrites one already stored from a previous poll."""
    now = datetime.now(timezone.utc)
    fetched = 0
    footprint_failed = 0

    for storm in storms:
        fields = parse_storm(storm)
        existing = session.get(RawNhcStorm, fields["id"])

        try:
            footprint = fetch_wind_radii_footprint(storm)
        except httpx.HTTPError:
            footprint = None
            footprint_failed += 1
        fields["wind_radii_geojson"] = footprint or (existing.wind_radii_geojson if existing else None)

        fields["last_polled_at"] = now
        fields["first_seen_at"] = existing.first_seen_at if existing else now

        session.merge(RawNhcStorm(**fields))
        fetched += 1

    session.commit()
    return {"fetched": fetched, "footprint_failed": footprint_failed}


def normalize_to_events(session: Session) -> int:
    """Normalise every row in raw_nhc_storms into the unified events table.
    Wind radii footprint (fetched in upsert_storms) is set here, same as
    wildfire's perimeter. Scoring is expensive-tier (NSI intersection, both
    axes - wind has no PAGER-equivalent published baseline for humanitarian
    the way earthquake does) and runs separately via score_events() - not
    computed here, and preserved rather than reset on every poll (same fix
    already applied to wildfire's normalize_to_events after the same bug
    was caught there)."""
    now = datetime.now(timezone.utc)
    raw_rows = session.execute(select(RawNhcStorm)).scalars().all()
    normalized = 0

    for raw in raw_rows:
        existing = session.get(Event, ("nhc", raw.id))
        name = f"{raw.classification} {raw.name}".strip() if raw.classification else raw.name

        event = Event(
            source="nhc",
            source_event_id=raw.id,
            peril="wind",
            name=name,
            event_time=existing.event_time if existing else now,
            last_updated=raw.last_update,
            longitude=raw.longitude,
            latitude=raw.latitude,
            footprint_geojson=raw.wind_radii_geojson,
            primary_metric_label="max_sustained_wind_kt",
            primary_metric_value=raw.intensity_kt,
            source_alert_level=None,
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
    """Expensive-tier scoring (NSI point-in-polygon intersection) for wind
    events - both axes, since wind has no PAGER-equivalent published
    humanitarian baseline the way earthquake does. Guarded the same way as
    wildfire's score_events(): only (re)scores an event never scored or
    whose footprint changed since. footprint_geojson is checked in Python,
    not SQL - a JSON column holding Python None is stored as the JSON value
    null, not SQL NULL, so a SQL-level null filter would silently match
    every row (caught and fixed for earthquake's score_economic() on
    2026-08-26 - same trap, avoided here from the start)."""
    now = datetime.now(timezone.utc)
    candidates = session.execute(select(Event).where(Event.peril == "wind")).scalars().all()
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

        event.humanitarian_score = scoring.humanitarian_score(exposure["population_exposed"])
        event.economic_score = scoring.economic_score(exposure["replacement_cost_usd"])
        event.overall_score = scoring.overall_score(event.humanitarian_score, event.economic_score)
        event.confidence = (
            f"NSI intersection (wind radii footprint), {exposure['structure_count']} structures found"
            if exposure["structure_count"] is not None
            else "no footprint available"
        )
        event.scored_at = now
        scored += 1

    session.commit()
    return {"scored": scored, "failed": failed, "remaining": max(0, len(needs_scoring) - scored)}


# --- Per-basin RSS feeds ---


def _parse_rss_item(item_el: ET.Element, basin: str) -> dict[str, Any]:
    def text(tag: str) -> str | None:
        el = item_el.find(tag)
        return el.text if el is not None else None

    cyclone_el = item_el.find(f"{{{NHC_XML_NS}}}Cyclone")
    cyclone_data = None
    if cyclone_el is not None:
        cyclone_data = {child.tag.split("}")[-1]: child.text for child in cyclone_el}

    guid_el = item_el.find("guid")
    guid = guid_el.text if guid_el is not None else None

    return {
        "guid": guid,
        "basin": basin,
        "title": text("title"),
        "link": text("link"),
        "pub_date": _parse_rfc822(text("pubDate")),
        "cyclone_data": cyclone_data,
        "raw_item": {
            "title": text("title"),
            "link": text("link"),
            "guid": guid,
            "pubDate": text("pubDate"),
            "description": text("description"),
        },
    }


def fetch_rss_items() -> list[dict]:
    items = []
    for basin, url in RSS_BASIN_URLS.items():
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item_el in root.findall(".//item"):
            items.append(_parse_rss_item(item_el, basin))
    return items


def upsert_rss_items(session: Session, items: list[dict]) -> dict[str, int]:
    """Stored as-is, not normalised into the unified events table - these
    are product announcements and storm-status headlines, not events in
    their own right. CurrentStorms.json (above) is what feeds the queue."""
    now = datetime.now(timezone.utc)
    fetched = 0
    skipped_no_guid = 0

    for fields in items:
        if not fields.get("guid"):
            skipped_no_guid += 1
            continue

        existing = session.get(RawNhcRssItem, fields["guid"])
        fields["last_polled_at"] = now
        fields["first_seen_at"] = existing.first_seen_at if existing else now

        session.merge(RawNhcRssItem(**fields))
        fetched += 1

    session.commit()
    return {"fetched": fetched, "skipped_no_guid": skipped_no_guid}
