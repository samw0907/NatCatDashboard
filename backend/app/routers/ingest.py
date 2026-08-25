# backend/app/routers/ingest.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import usgs
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
