# backend/app/routers/events.py

from fastapi import APIRouter, Depends
from sqlalchemy import nulls_last, select
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
    """Read of the unified events table, ranked by overall score (nulls
    last) - proves the pipeline actually produces a ranked queue, not just
    a normalised table. Only sorted by overall score for now; sorting by a
    chosen axis and filtering by peril (plan section 8.3) is Phase 5."""
    events = (
        db.execute(select(Event).order_by(nulls_last(Event.overall_score.desc())))
        .scalars()
        .all()
    )
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
            "humanitarian_score": e.humanitarian_score,
            "economic_score": e.economic_score,
            "overall_score": e.overall_score,
            "confidence": e.confidence,
        }
        for e in events
    ]
