# backend/tests/test_pruning.py

from datetime import datetime, timedelta, timezone

from app import pruning
from app.models import Event, RawNifcEvent, RawUsgsEvent

NOW = datetime.now(timezone.utc)


def _usgs(db, event_id, age_days):
    t = NOW - timedelta(days=age_days)
    db.add(RawUsgsEvent(id=event_id, event_time=t, raw_properties={}, first_seen_at=t, last_polled_at=NOW))
    db.add(Event(source="usgs", source_event_id=event_id, peril="earthquake", event_time=t,
                 first_seen_at=t, last_synced_at=NOW))


def _nifc(db, event_id, discovered_days_ago, last_polled_days_ago):
    discovered = NOW - timedelta(days=discovered_days_ago)
    polled = NOW - timedelta(days=last_polled_days_ago)
    db.add(RawNifcEvent(id=event_id, discovery_time=discovered, raw_properties={},
                        first_seen_at=discovered, last_polled_at=polled))
    db.add(Event(source="nifc", source_event_id=event_id, peril="wildfire", event_time=discovered,
                 first_seen_at=discovered, last_synced_at=polled))


def test_dry_run_deletes_nothing(db):
    _usgs(db, "old", 20)
    db.commit()

    result = pruning.prune_usgs(db, dry_run=True)

    assert result["candidates"] == 1 and result["deleted"] == 0
    assert db.get(RawUsgsEvent, "old") is not None


def test_usgs_is_pruned_by_event_age_from_both_tables(db):
    _usgs(db, "old", 20)
    _usgs(db, "recent", 2)
    db.commit()

    result = pruning.prune_usgs(db, dry_run=False)

    assert result["deleted"] == 1
    assert db.get(RawUsgsEvent, "old") is None and db.get(Event, ("usgs", "old")) is None
    assert db.get(RawUsgsEvent, "recent") is not None


def test_long_burning_wildfire_survives_while_still_in_the_feed(db):
    # Discovered 60 days ago but seen in today's poll: must not be pruned.
    _nifc(db, "still-burning", discovered_days_ago=60, last_polled_days_ago=0)
    # Gone from the feed for 5 days: over.
    _nifc(db, "out", discovered_days_ago=10, last_polled_days_ago=5)
    db.commit()

    result = pruning.prune_nifc(db, dry_run=False)

    assert result["deleted"] == 1
    assert db.get(RawNifcEvent, "still-burning") is not None
    assert db.get(RawNifcEvent, "out") is None and db.get(Event, ("nifc", "out")) is None


def test_prune_all_defaults_to_dry_run(db):
    _usgs(db, "old", 20)
    db.commit()
    assert pruning.prune_all(db)["dry_run"] is True
    assert db.get(RawUsgsEvent, "old") is not None
