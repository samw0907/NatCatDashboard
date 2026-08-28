# backend/app/pruning.py
#
# Rolling-window pruning (plan section 8.1, ingest step 6). O1 resolved
# 2026-08-28: split by source rather than one blanket age rule.
#
# Earthquake and GDACS are age-based - both are fetched as a bounded time
# window already (14 days), so a row older than that window is genuinely
# out of scope, not just old.
#
# Wildfire and wind are presence-based instead. Their event_time/discovery
# date can be old while the incident is still very much current (a large
# wildfire can burn for weeks; NIFC's discovery_time reflects when it
# started, not whether it's still active). The signal that actually means
# "this is over" is absence from the source's own current-state feed -
# tracked here via last_polled_at, not event age.
#
# DESTRUCTIVE OPERATION: every function here defaults to dry_run=True and
# must be reviewed before being run for real, per Sam's working
# preferences and the plan's explicit requirement to flag deletion
# routines in detail before first use.

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Event, RawGdacsEvent, RawNhcRssItem, RawNhcStorm, RawNifcEvent, RawUsgsEvent

USGS_WINDOW_DAYS = 14
GDACS_WINDOW_DAYS = 14
NIFC_GRACE_DAYS = 3
NHC_GRACE_DAYS = 2


def prune_usgs(session: Session, days: int = USGS_WINDOW_DAYS, dry_run: bool = True) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stale = session.execute(select(RawUsgsEvent).where(RawUsgsEvent.event_time < cutoff)).scalars().all()
    ids = [r.id for r in stale]

    if not dry_run and ids:
        for r in stale:
            session.delete(r)
        session.execute(delete(Event).where(Event.source == "usgs", Event.source_event_id.in_(ids)))
        session.commit()

    return {
        "source": "usgs",
        "rule": f"event_time older than {days} days",
        "candidates": len(ids),
        "deleted": 0 if dry_run else len(ids),
        "dry_run": dry_run,
        "sample_ids": ids[:5],
    }


def prune_gdacs(session: Session, days: int = GDACS_WINDOW_DAYS, dry_run: bool = True) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stale = session.execute(select(RawGdacsEvent).where(RawGdacsEvent.to_date < cutoff)).scalars().all()

    if not dry_run:
        for r in stale:
            session.delete(r)
        session.commit()

    return {
        "source": "gdacs",
        "rule": f"to_date older than {days} days",
        "candidates": len(stale),
        "deleted": 0 if dry_run else len(stale),
        "dry_run": dry_run,
        # GDACS is never normalised into Event (D8) - nothing else to prune alongside it.
    }


def prune_nifc(session: Session, grace_days: int = NIFC_GRACE_DAYS, dry_run: bool = True) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=grace_days)
    stale = session.execute(select(RawNifcEvent).where(RawNifcEvent.last_polled_at < cutoff)).scalars().all()
    ids = [r.id for r in stale]

    if not dry_run and ids:
        for r in stale:
            session.delete(r)
        session.execute(delete(Event).where(Event.source == "nifc", Event.source_event_id.in_(ids)))
        session.commit()

    return {
        "source": "nifc",
        "rule": f"not seen in a poll for {grace_days} days (presence-based, not event age)",
        "candidates": len(ids),
        "deleted": 0 if dry_run else len(ids),
        "dry_run": dry_run,
        "sample_ids": ids[:5],
    }


def prune_nhc(session: Session, grace_days: int = NHC_GRACE_DAYS, dry_run: bool = True) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=grace_days)
    stale_storms = session.execute(select(RawNhcStorm).where(RawNhcStorm.last_polled_at < cutoff)).scalars().all()
    storm_ids = [r.id for r in stale_storms]

    stale_rss = session.execute(select(RawNhcRssItem).where(RawNhcRssItem.last_polled_at < cutoff)).scalars().all()
    rss_guids = [r.guid for r in stale_rss]

    if not dry_run:
        for r in stale_storms:
            session.delete(r)
        if storm_ids:
            session.execute(delete(Event).where(Event.source == "nhc", Event.source_event_id.in_(storm_ids)))
        for r in stale_rss:
            session.delete(r)
        session.commit()

    return {
        "source": "nhc",
        "rule": f"not seen in a poll for {grace_days} days (presence-based, not event age)",
        "storm_candidates": len(storm_ids),
        "storm_deleted": 0 if dry_run else len(storm_ids),
        "rss_candidates": len(rss_guids),
        "rss_deleted": 0 if dry_run else len(rss_guids),
        "dry_run": dry_run,
        "sample_storm_ids": storm_ids[:5],
    }


def prune_all(session: Session, dry_run: bool = True) -> dict[str, Any]:
    return {
        "dry_run": dry_run,
        "usgs": prune_usgs(session, dry_run=dry_run),
        "gdacs": prune_gdacs(session, dry_run=dry_run),
        "nifc": prune_nifc(session, dry_run=dry_run),
        "nhc": prune_nhc(session, dry_run=dry_run),
    }
