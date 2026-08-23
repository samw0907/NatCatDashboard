# backend/app/db.py

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


# Engine creation is lazy (unlike WildfireDashboard's module-level engine) so
# that importing this module - and anything that imports it, including the
# FastAPI app itself - doesn't require DATABASE_URL to be set. Railway
# Postgres doesn't exist yet for this project; this keeps the app and its
# models testable against a throwaway local database in the meantime.
@lru_cache
def get_engine():
    return create_engine(get_settings().sqlalchemy_database_url, pool_pre_ping=True)


def get_session() -> Session:
    session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return session_factory()
