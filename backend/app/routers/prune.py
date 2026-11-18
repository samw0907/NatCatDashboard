# backend/app/routers/prune.py
#
# Not wired into the automatic ingest endpoints yet - triggered manually
# only, until dry-run results have been reviewed and confirmed correct.
# `dry_run` defaults to True so a naive call is always safe; deletion only
# happens when it's explicitly passed as false.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import pruning
from ..auth import require_admin_token
from ..db import get_session

router = APIRouter(prefix="/api", dependencies=[Depends(require_admin_token)])


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


@router.post("/prune")
def prune(dry_run: bool = True, db: Session = Depends(get_db)):
    return pruning.prune_all(db, dry_run=dry_run)
