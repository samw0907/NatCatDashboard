# backend/tests/test_nhc.py

from shapely.geometry import shape

from app import nhc
from app.models import Event, RawNhcRssItem

from .conftest import FIXTURES, load_json


def test_wind_radii_footprint_is_read_from_the_shapefile_zip(fake_http):
    fake_http({".zip": "nhc_wind_radii.zip"})
    storm = load_json("nhc_current_storms.json")["activeStorms"][0]

    footprint = nhc.fetch_wind_radii_footprint(storm)

    assert footprint is not None
    geom = shape(footprint)
    assert geom.is_valid and geom.area > 0


def test_storm_without_wind_radii_product_has_no_footprint():
    assert nhc.fetch_wind_radii_footprint({"id": "al012026"}) is None


def test_upsert_and_normalize_storms(db, fake_http):
    fake_http({".zip": "nhc_wind_radii.zip"})
    storms = load_json("nhc_current_storms.json")["activeStorms"]

    assert nhc.upsert_storms(db, storms) == {"fetched": len(storms), "footprint_failed": 0}
    assert nhc.normalize_to_events(db) == len(storms)

    for storm in storms:
        event = db.get(Event, ("nhc", storm["id"]))
        assert event.peril == "wind"
        assert event.primary_metric_label == "max_sustained_wind_kt"
        assert event.footprint_geojson is not None


def test_rss_summary_items_carry_cyclone_headline(db, monkeypatch):
    import xml.etree.ElementTree as ET

    root = ET.fromstring((FIXTURES / "nhc_rss_cp.xml").read_bytes())
    items = [nhc._parse_rss_item(el, "cp") for el in root.findall(".//item")]

    assert items and all(item["guid"] for item in items)
    summaries = [item for item in items if item["guid"].startswith("summary-")]
    assert summaries and all(item["cyclone_data"] for item in summaries)

    assert nhc.upsert_rss_items(db, items)["fetched"] == len(items)
    assert db.query(RawNhcRssItem).count() == len({item["guid"] for item in items})
