# backend/app/usgs.py

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import scoring
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


def _score_earthquake(raw: RawUsgsEvent) -> tuple[float | None, float | None, float | None, str]:
    """O4/O5 resolved 2026-08-25 (plan section 6.3). Humanitarian axis:
    PAGER's own MMI-banded population exposure, weighted by intensity, fed
    through the shared continuous log-scale score (scoring.py). Economic
    axis stays null - it needs NSI point-in-polygon intersection against a
    real footprint, and earthquake has none yet (ShakeMap's MMI contour
    isn't fetched) - deliberately deferred, not forgotten, per the
    2026-08-25 sequencing decision to score what's ready now rather than
    block on fetching two more kinds of hazard-footprint geometry first.
    Only covers the minority of events with a losspager product."""
    if raw.alert is None:
        return None, None, None, "no PAGER product available"

    exposure = _weighted_population_exposure(raw.pager_population_exposure)
    humanitarian = scoring.humanitarian_score(exposure)
    economic = None
    overall = scoring.overall_score(humanitarian, economic)
    confidence = (
        "humanitarian axis only - no footprint geometry yet for the economic axis"
        if humanitarian is not None
        else "PAGER product present but no usable population exposure data"
    )
    return humanitarian, economic, overall, confidence


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
        humanitarian_score, economic_score, overall_score, confidence = _score_earthquake(raw)
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
            # Earthquake scoring is cheap (reuses already-fetched PAGER
            # data, no new external call) so it can safely run on every
            # normalisation pass, unlike wildfire's NSI-dependent scoring.
            scored_at=now,
            first_seen_at=existing.first_seen_at if existing else now,
            last_synced_at=now,
        )
        session.merge(event)
        normalized += 1

    session.commit()
    return normalized
