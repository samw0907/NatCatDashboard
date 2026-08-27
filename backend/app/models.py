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

    # PAGER losspager enrichment, plus the ShakeMap MMI contour - both
    # populated only when `alert` is not null (see fetch_enrichment in
    # usgs.py for the screening logic and how the contour is built).
    pager_total_fatalities: Mapped[int | None] = mapped_column(Integer)
    pager_total_economic_loss_usd: Mapped[int | None] = mapped_column(BigInteger)
    pager_population_exposure: Mapped[dict | None] = mapped_column(JSON)
    # Polygon (GeoJSON) for the area shaking at or above MIN_FOOTPRINT_MMI,
    # built from ShakeMap's contour lines - null if no shakemap product, or
    # no contour reaches that intensity.
    mmi_contour_geojson: Mapped[dict | None] = mapped_column(JSON)
    enrichment_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_polled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RawNhcStorm(Base):
    """Raw NHC active-storm records from CurrentStorms.json, one row per
    storm - see plan section 5.2 (2026-08-25 revision)."""

    __tablename__ = "raw_nhc_storms"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # e.g. "cp012026"

    name: Mapped[str | None] = mapped_column(String)
    classification: Mapped[str | None] = mapped_column(String)  # "TS", "HU", etc
    intensity_kt: Mapped[float | None] = mapped_column(Float)
    pressure_mb: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    movement_dir: Mapped[float | None] = mapped_column(Float)
    movement_speed_kt: Mapped[float | None] = mapped_column(Float)
    advisory_num: Mapped[str | None] = mapped_column(String)
    last_update: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Polygon (GeoJSON) for the current wind field at the lowest available
    # speed threshold (broadest extent, e.g. 34kt if present) - from the
    # initialWindExtent shapefile, current radii not forecast, staying
    # consistent with earthquake/wildfire representing current state.
    wind_radii_geojson: Mapped[dict | None] = mapped_column(JSON)
    # Full raw storm object, including every other GIS product URL
    # (track/cone/surge KMZ+ZIP links) - not parsed out into columns since
    # none are fetched yet, but kept so a later phase can read them
    # straight from here.
    raw_properties: Mapped[dict] = mapped_column(JSON)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_polled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RawNhcRssItem(Base):
    """Raw items from NHC's per-basin RSS feeds (gis-at.xml, gis-ep.xml,
    gis-cp.xml) - ingested and stored alongside CurrentStorms.json rather
    than instead of it (plan section 5.2, 2026-08-23 decision), since most
    items just re-announce the same GIS products CurrentStorms.json links
    to directly, but "summary-*" items carry a human-readable NHC headline
    (via cyclone_data) that CurrentStorms.json doesn't have at all."""

    __tablename__ = "raw_nhc_rss_items"

    guid: Mapped[str] = mapped_column(String, primary_key=True)

    basin: Mapped[str] = mapped_column(String)  # "at", "ep", "cp"
    title: Mapped[str | None] = mapped_column(String)
    link: Mapped[str | None] = mapped_column(String)
    pub_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Parsed from the <nhc:Cyclone> element, present only on "summary-*"
    # items.
    cyclone_data: Mapped[dict | None] = mapped_column(JSON)
    raw_item: Mapped[dict] = mapped_column(JSON)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_polled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RawGdacsEvent(Base):
    """Raw GDACS event records, stored per plan D8 - ingested and kept for
    a possible future comparison use (O14), but never wired into scoring
    or the UI. Scoped to the three perils this project tracks (EQ, TC, WF)
    rather than all seven GDACS hazard types - flood/volcano/drought/
    tsunami would have nothing of ours to compare against. Global, not
    filtered to the US - GDACS's SEARCH endpoint offers no geographic
    filter, and filtering client-side would be premature before O14
    actually decides what this data gets used for, if anything.

    Keyed on (event_id, episode_id) rather than event_id alone - GDACS
    events accumulate episodes as they develop (e.g. a cyclone's
    advisories), and each episode can carry a different alert level. This
    naturally preserves that history across repeated polls rather than
    only keeping the latest state."""

    __tablename__ = "raw_gdacs_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    episode_id: Mapped[str] = mapped_column(String, primary_key=True)

    event_type: Mapped[str | None] = mapped_column(String)  # "EQ", "TC", "WF"
    name: Mapped[str | None] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String)
    alert_level: Mapped[str | None] = mapped_column(String)  # Green/Orange/Red
    from_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    to_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    severity_value: Mapped[float | None] = mapped_column(Float)
    severity_text: Mapped[str | None] = mapped_column(String)
    severity_unit: Mapped[str | None] = mapped_column(String)
    raw_properties: Mapped[dict] = mapped_column(JSON)

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

    # Scoring (plan section 6, O4/O5 resolved 2026-08-25 - see scoring.py).
    humanitarian_score: Mapped[float | None] = mapped_column(Float)
    economic_score: Mapped[float | None] = mapped_column(Float)
    overall_score: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[str | None] = mapped_column(String)
    # When scoring last actually ran for this event - distinct from
    # last_synced_at (which updates on every cheap normalisation pass).
    # Scoring that depends on an external call (NSI intersection) is
    # expensive-tier and shouldn't rerun just because normalisation did;
    # this is what a rescore guard checks against last_updated to decide
    # whether the underlying hazard footprint actually changed.
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RawNifcEvent(Base):
    """Raw NIFC WFIGS wildfire perimeter records, one row per incident,
    shaped to WFIGS's own field structure - see plan section 8.1."""

    __tablename__ = "raw_nifc_events"

    # IRWIN ID - the standard cross-agency wildfire incident identifier.
    id: Mapped[str] = mapped_column(String, primary_key=True)

    incident_name: Mapped[str | None] = mapped_column(String)
    # GIS-calculated acreage from the actual perimeter polygon we store
    # below - kept separate from the self-reported incident_size since the
    # two can diverge; gis_acres is what's internally consistent with the
    # stored geometry.
    gis_acres: Mapped[float | None] = mapped_column(Float)
    incident_size: Mapped[float | None] = mapped_column(Float)
    discovery_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    date_current: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    percent_contained: Mapped[float | None] = mapped_column(Float)
    fire_cause: Mapped[str | None] = mapped_column(String)
    complexity_level: Mapped[str | None] = mapped_column(String)
    poo_state: Mapped[str | None] = mapped_column(String)
    geometry: Mapped[dict | None] = mapped_column(JSON)
    raw_properties: Mapped[dict] = mapped_column(JSON)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_polled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
