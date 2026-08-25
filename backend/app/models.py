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


class Event(Base):
    """The unified table every source's ingest normalises into - see plan
    section 8.1. Deliberately generic: peril-specific detail stays in each
    source's own raw table, this is only what's needed to rank and display
    events across perils.

    Primary key is (source, source_event_id) rather than a synthetic id, so
    upserts are a straightforward keyed merge and the link back to the raw
    row - where the full detail actually lives - is never ambiguous."""

    __tablename__ = "events"

    source: Mapped[str] = mapped_column(String, primary_key=True)  # "usgs", "nhc", "nifc"
    source_event_id: Mapped[str] = mapped_column(String, primary_key=True)

    peril: Mapped[str] = mapped_column(String)  # "earthquake", "wind", "wildfire"
    name: Mapped[str | None] = mapped_column(String)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    # Real hazard footprint (GeoJSON), where one exists - null until a
    # peril-specific footprint source is wired in. For earthquake the
    # natural footprint is the ShakeMap MMI contour, not yet fetched; this
    # is deliberately deferred to Phase 3, when NSI point-in-polygon
    # intersection actually needs a real boundary to query against.
    footprint_geojson: Mapped[dict | None] = mapped_column(JSON)

    # Peril-specific severity headline, kept as a labelled pair rather than
    # forcing incompatible units (magnitude, knots, acres) into one column.
    primary_metric_label: Mapped[str | None] = mapped_column(String)
    primary_metric_value: Mapped[float | None] = mapped_column(Float)

    # The source's own published alert/severity band, where one exists -
    # e.g. PAGER's colour for earthquake - kept alongside our own scores
    # below for the comparison plan section 6.4 calls for.
    source_alert_level: Mapped[str | None] = mapped_column(String)

    # Scoring (plan section 6) - null until Phase 1(d)/Phase 3 wires it in.
    humanitarian_score: Mapped[float | None] = mapped_column(Float)
    economic_score: Mapped[float | None] = mapped_column(Float)
    overall_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[str | None] = mapped_column(String)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
