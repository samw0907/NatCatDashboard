# backend/app/nhc.py

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

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
    now = datetime.now(timezone.utc)
    fetched = 0

    for storm in storms:
        fields = parse_storm(storm)
        existing = session.get(RawNhcStorm, fields["id"])
        fields["last_polled_at"] = now
        fields["first_seen_at"] = existing.first_seen_at if existing else now

        session.merge(RawNhcStorm(**fields))
        fetched += 1

    session.commit()
    return {"fetched": fetched}


def normalize_to_events(session: Session) -> int:
    """Normalise every row in raw_nhc_storms into the unified events table.
    Like earthquake, no real footprint geometry yet - a storm's track cone
    and wind radii are the natural footprint, and those are expensive-tier
    GIS product downloads (linked in raw_properties, not fetched here),
    deferred the same way ShakeMap contours are for earthquake."""
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
            footprint_geojson=None,
            primary_metric_label="max_sustained_wind_kt",
            primary_metric_value=raw.intensity_kt,
            source_alert_level=None,
            humanitarian_score=None,
            economic_score=None,
            overall_score=None,
            confidence="not yet scored (Phase 3)",
            first_seen_at=existing.first_seen_at if existing else now,
            last_synced_at=now,
        )
        session.merge(event)
        normalized += 1

    session.commit()
    return normalized


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
