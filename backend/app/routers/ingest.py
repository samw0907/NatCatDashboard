# backend/app/routers/ingest.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import gdacs, nhc, nifc, usgs
from ..db import get_session

router = APIRouter(prefix="/api")


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


@router.post("/ingest/usgs")
def ingest_usgs(days: int = 14, score_limit: int = 20, db: Session = Depends(get_db)):
    features = usgs.fetch_summary(days=days)
    result = usgs.upsert_events(db, features)
    result["normalized"] = usgs.normalize_to_events(db)
    result["economic_scoring"] = usgs.score_economic(db, limit=score_limit)
    return result


@router.post("/ingest/nifc")
def ingest_nifc(score_limit: int = 20, db: Session = Depends(get_db)):
    features = nifc.fetch_perimeters()
    result = nifc.upsert_events(db, features)
    result["normalized"] = nifc.normalize_to_events(db)
    result["scoring"] = nifc.score_events(db, limit=score_limit)
    return result


@router.post("/ingest/nhc")
def ingest_nhc(db: Session = Depends(get_db)):
    storms = nhc.fetch_current_storms()
    result = nhc.upsert_storms(db, storms)
    result["normalized"] = nhc.normalize_to_events(db)

    rss_items = nhc.fetch_rss_items()
    result["rss"] = nhc.upsert_rss_items(db, rss_items)
    return result


@router.post("/ingest/gdacs")
def ingest_gdacs(days: int = 14, db: Session = Depends(get_db)):
    """Raw storage only - never normalised into the unified events table
    (D8). No corresponding GET endpoint yet either; nothing reads this
    data until O14 decides it should."""
    features = gdacs.fetch_events(days=days)
    return gdacs.upsert_events(db, features)
