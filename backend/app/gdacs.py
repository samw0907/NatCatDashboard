# backend/app/gdacs.py

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from .models import RawGdacsEvent

SEARCH_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"

# Scoped to the three perils this project actually tracks (plan D4) rather
# than all seven GDACS hazard types - see RawGdacsEvent's docstring.
EVENT_TYPES = "EQ;TC;WF"


def _parse_gdacs_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_events(days: int = 14) -> list[dict]:
    fromdate = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    todate = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    params = {"eventlist": EVENT_TYPES, "fromdate": fromdate, "todate": todate}
    resp = httpx.get(SEARCH_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("features", [])


def parse_feature(feature: dict) -> dict[str, Any]:
    props = feature["properties"]
    severity = props.get("severitydata") or {}
    event_id = props.get("eventid")
    episode_id = props.get("episodeid")
    return {
        "event_id": str(event_id) if event_id is not None else None,
        "episode_id": str(episode_id) if episode_id is not None else None,
        "event_type": props.get("eventtype"),
        "name": props.get("name"),
        "country": props.get("country"),
        "alert_level": props.get("alertlevel"),
        "from_date": _parse_gdacs_date(props.get("fromdate")),
        "to_date": _parse_gdacs_date(props.get("todate")),
        "severity_value": severity.get("severity"),
        "severity_text": severity.get("severitytext"),
        "severity_unit": severity.get("severityunit"),
        "raw_properties": props,
    }


def upsert_events(session: Session, features: list[dict]) -> dict[str, int]:
    """Stored only - never normalised into the unified events table (D8).
    A feature missing either id can't be keyed - skipped and counted
    rather than guessing, same discipline as the NIFC ingest."""
    now = datetime.now(timezone.utc)
    fetched = 0
    skipped_no_id = 0

    for feature in features:
        fields = parse_feature(feature)
        if not fields["event_id"] or not fields["episode_id"]:
            skipped_no_id += 1
            continue

        existing = session.get(RawGdacsEvent, (fields["event_id"], fields["episode_id"]))
        fields["last_polled_at"] = now
        fields["first_seen_at"] = existing.first_seen_at if existing else now

        session.merge(RawGdacsEvent(**fields))
        fetched += 1

    session.commit()
    return {"fetched": fetched, "skipped_no_id": skipped_no_id}
