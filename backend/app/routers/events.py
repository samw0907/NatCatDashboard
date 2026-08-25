# backend/app/routers/events.py

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Event

router = APIRouter(prefix="/api")


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


@router.get("/events")
def list_events(db: Session = Depends(get_db)):
    """Minimal read of the unified events table - proves normalisation
    worked, and is the foundation the queue view (plan section 8.3) will
    build on. No sorting/filtering yet - that's Phase 5."""
    events = db.execute(select(Event)).scalars().all()
    return [
        {
            "source": e.source,
            "source_event_id": e.source_event_id,
            "peril": e.peril,
            "name": e.name,
            "event_time": e.event_time.isoformat() if e.event_time else None,
            "longitude": e.longitude,
            "latitude": e.latitude,
            "primary_metric_label": e.primary_metric_label,
            "primary_metric_value": e.primary_metric_value,
            "source_alert_level": e.source_alert_level,
            "overall_score": e.overall_score,
        }
        for e in events
    ]
