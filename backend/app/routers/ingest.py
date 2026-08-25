# backend/app/routers/ingest.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import nhc, nifc, usgs
from ..db import get_session

router = APIRouter(prefix="/api")


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


@router.post("/ingest/usgs")
def ingest_usgs(days: int = 14, db: Session = Depends(get_db)):
    features = usgs.fetch_summary(days=days)
    result = usgs.upsert_events(db, features)
    result["normalized"] = usgs.normalize_to_events(db)
    return result


@router.post("/ingest/nifc")
def ingest_nifc(db: Session = Depends(get_db)):
    features = nifc.fetch_perimeters()
    result = nifc.upsert_events(db, features)
    result["normalized"] = nifc.normalize_to_events(db)
    return result


@router.post("/ingest/nhc")
def ingest_nhc(db: Session = Depends(get_db)):
    storms = nhc.fetch_current_storms()
    result = nhc.upsert_storms(db, storms)
    result["normalized"] = nhc.normalize_to_events(db)

    rss_items = nhc.fetch_rss_items()
    result["rss"] = nhc.upsert_rss_items(db, rss_items)
    return result
