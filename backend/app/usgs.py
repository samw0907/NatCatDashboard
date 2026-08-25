# backend/app/usgs.py

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

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


def fetch_losspager_enrichment(detail_url: str) -> dict[str, Any] | None:
    """Two-tier fetch: given an event's detail feed URL, fetch the losspager
    product's exposures.json and losses.json contents. Returns None if the
    event has no losspager product."""
    resp = httpx.get(detail_url, timeout=30)
    resp.raise_for_status()
    detail = resp.json()
    losspager = detail.get("properties", {}).get("products", {}).get("losspager")
    if not losspager:
        return None

    contents = losspager[0].get("contents", {})
    exposures_url = contents.get("json/exposures.json", {}).get("url")
    losses_url = contents.get("json/losses.json", {}).get("url")
    if not exposures_url or not losses_url:
        return None

    exposures = httpx.get(exposures_url, timeout=30).json()
    losses = httpx.get(losses_url, timeout=30).json()

    return {
        "population_exposure": exposures.get("population_exposure"),
        "total_fatalities": losses.get("empirical_fatality", {}).get("total_fatalities"),
        "total_economic_loss_usd": losses.get("empirical_economic", {}).get("total_dollars"),
    }


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
            "enrichment_fetched_at": existing.enrichment_fetched_at if existing else None,
        }
        if fields["alert"] is not None and fields["detail_url"]:
            try:
                enrichment = fetch_losspager_enrichment(fields["detail_url"])
            except httpx.HTTPError:
                enrichment = None
                enrichment_failed += 1
            if enrichment:
                enrichment_fields = {
                    "pager_population_exposure": enrichment["population_exposure"],
                    "pager_total_fatalities": enrichment["total_fatalities"],
                    "pager_total_economic_loss_usd": enrichment["total_economic_loss_usd"],
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


# PAGER's own published alert thresholds (plan section 4.1) - reused
# directly rather than inventing new bands. This is Phase 1's placeholder
# scoring, using only what PAGER already computed for us. The real
# multi-source formulation (O4/O5) is Phase 3's job, once NSI is wired in
# and every event - not just the minority with a PAGER product - can be
# scored the same way.
_FATALITY_BANDS = (1, 100, 1000)  # yellow, orange, red thresholds
_ECONOMIC_BANDS_USD = (1_000_000, 100_000_000, 1_000_000_000)


def _pager_band(value: float | None, bands: tuple[float, float, float]) -> int | None:
    """0 (green) to 3 (red), using PAGER's own thresholds."""
    if value is None:
        return None
    yellow, orange, red = bands
    if value >= red:
        return 3
    if value >= orange:
        return 2
    if value >= yellow:
        return 1
    return 0


def _score_from_pager(raw: RawUsgsEvent) -> tuple[float | None, float | None, float | None, str]:
    """Bands PAGER's own fatality and economic-loss numbers separately,
    kept as two genuinely distinct axes (plan section 6.2) rather than
    duplicating the single combined `alert` colour into both. Only covers
    the minority of events with a losspager product - everything else
    stays unscored with an honest confidence note (section 6.3), rather
    than a fabricated number."""
    if raw.alert is None:
        return None, None, None, "no PAGER product available"

    humanitarian = _pager_band(raw.pager_total_fatalities, _FATALITY_BANDS)
    economic = _pager_band(raw.pager_total_economic_loss_usd, _ECONOMIC_BANDS_USD)
    present = [s for s in (humanitarian, economic) if s is not None]
    overall = max(present) if present else None
    return (
        humanitarian,
        economic,
        overall,
        "Phase 1 placeholder - PAGER-band-derived, not the full O4/O5 formulation",
    )


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
        humanitarian_score, economic_score, overall_score, confidence = _score_from_pager(raw)
        event = Event(
            source="usgs",
            source_event_id=raw.id,
            peril="earthquake",
            name=raw.title or raw.place,
            event_time=raw.event_time,
            last_updated=raw.updated,
            longitude=raw.longitude,
            latitude=raw.latitude,
            # No real footprint geometry yet - see the Event model's
            # docstring and plan section 8.1. Left null deliberately rather
            # than approximated with an invented radius.
            footprint_geojson=None,
            primary_metric_label="magnitude",
            primary_metric_value=raw.mag,
            source_alert_level=raw.alert,
            humanitarian_score=humanitarian_score,
            economic_score=economic_score,
            overall_score=overall_score,
            confidence=confidence,
            first_seen_at=existing.first_seen_at if existing else now,
            last_synced_at=now,
        )
        session.merge(event)
        normalized += 1

    session.commit()
    return normalized
