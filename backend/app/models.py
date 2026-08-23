# backend/app/models.py

from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class RawUsgsEvent(Base):
    """Raw USGS earthquake records, one row per event, shaped to USGS's own
    summary-feed and PAGER losspager structure rather than a normalised
    schema - see plan section 8.1."""

    __tablename__ = "raw_usgs_events"

    # USGS's own event id, e.g. "us6000tjl2" - globally unique, used as-is.
    id: Mapped[str] = mapped_column(String, primary_key=True)

    mag: Mapped[float | None] = mapped_column(Float)
    place: Mapped[str | None] = mapped_column(String)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    felt: Mapped[int | None] = mapped_column(Integer)
    cdi: Mapped[float | None] = mapped_column(Float)
    mmi: Mapped[float | None] = mapped_column(Float)
    # PAGER alert colour from the summary feed - null for most events (only
    # populated where PAGER actually ran, roughly M5.5+ globally).
    alert: Mapped[str | None] = mapped_column(String)
    sig: Mapped[int | None] = mapped_column(Integer)
    tsunami: Mapped[bool] = mapped_column(Boolean, default=False)
    event_type: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String)
    detail_url: Mapped[str | None] = mapped_column(String)
    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    depth_km: Mapped[float | None] = mapped_column(Float)
    # Full raw properties blob from the summary feed, for fidelity - so what
    # USGS actually said is always recoverable, not just our interpretation.
    raw_properties: Mapped[dict] = mapped_column(JSON)

    # PAGER losspager enrichment - populated only when `alert` is not null
    # (see fetch_losspager_enrichment in usgs.py for the screening logic).
    pager_total_fatalities: Mapped[int | None] = mapped_column(Integer)
    pager_total_economic_loss_usd: Mapped[int | None] = mapped_column(BigInteger)
    pager_population_exposure: Mapped[dict | None] = mapped_column(JSON)
    enrichment_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_polled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
