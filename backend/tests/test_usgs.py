# backend/tests/test_usgs.py

import httpx
from shapely.geometry import shape

from app import scoring, usgs
from app.models import Event, RawUsgsEvent

from .conftest import load_json

ENRICHMENT_ROUTES = {
    "exposures.json": "usgs_exposures.json",
    "losses.json": "usgs_losses.json",
    "cont_mmi.json": "usgs_cont_mmi.json",
    "/detail/": "usgs_event_detail.json",
}


def test_parse_feature_maps_core_fields():
    feature = load_json("usgs_summary_feed.json")["features"][0]
    fields = usgs.parse_feature(feature)
    assert fields["id"] == feature["id"]
    assert fields["mag"] == feature["properties"]["mag"]
    assert fields["event_time"].tzinfo is not None
    assert fields["raw_properties"] is feature["properties"]


def test_mmi_contour_polygon_builds_a_valid_footprint():
    polygon = usgs._mmi_contour_polygon(load_json("usgs_cont_mmi.json"), usgs.MIN_FOOTPRINT_MMI)
    assert polygon is not None
    geom = shape(polygon)
    assert geom.is_valid and geom.area > 0


def test_mmi_contour_polygon_is_none_above_available_levels():
    assert usgs._mmi_contour_polygon(load_json("usgs_cont_mmi.json"), 9.0) is None


def test_weighted_exposure_only_counts_mmi_four_and_up():
    exposure = {"mmi": [1, 2, 3, 4, 5], "aggregated_exposure": [1000, 1000, 1000, 10, 20]}
    assert usgs._weighted_population_exposure(exposure) == 10 * 1 + 20 * 2
    assert usgs._weighted_population_exposure({"mmi": [1, 2], "aggregated_exposure": [5, 5]}) is None


def test_fetch_enrichment_reads_pager_and_shakemap(fake_http):
    fake_http(ENRICHMENT_ROUTES)
    result = usgs.fetch_enrichment("https://earthquake.usgs.gov/fdsnws/event/1/detail/us6000tjl2.geojson")
    assert result["population_exposure"]["mmi"]
    assert result["total_fatalities"] is not None
    assert result["total_economic_loss_usd"] is not None
    assert result["mmi_contour_geojson"] is not None


def test_upsert_enriches_only_events_with_a_pager_alert(db, fake_http):
    features = load_json("usgs_summary_feed.json")["features"]
    fake = fake_http(ENRICHMENT_ROUTES)

    result = usgs.upsert_events(db, features)

    with_alert = [f for f in features if f["properties"]["alert"] is not None]
    assert result["fetched"] == len(features)
    assert result["enriched"] == len(with_alert)
    detail_calls = [url for url, _ in fake.calls if "/detail/" in url]
    assert len(detail_calls) == len(with_alert)


def test_repoll_keeps_enrichment_when_fetch_fails(db, fake_http, monkeypatch):
    features = load_json("usgs_summary_feed.json")["features"]
    fake_http(ENRICHMENT_ROUTES)
    usgs.upsert_events(db, features)
    target = next(f for f in features if f["properties"]["alert"] is not None)
    before = db.get(RawUsgsEvent, target["id"]).pager_population_exposure

    def failing(url, *args, **kwargs):
        raise httpx.ConnectError("feed down")

    monkeypatch.setattr(httpx, "get", failing)
    result = usgs.upsert_events(db, [target])

    assert result["enrichment_failed"] == 1
    assert db.get(RawUsgsEvent, target["id"]).pager_population_exposure == before


def test_normalize_scores_humanitarian_axis_only_where_pager_exists(db, fake_http):
    features = load_json("usgs_summary_feed.json")["features"]
    fake_http(ENRICHMENT_ROUTES)
    usgs.upsert_events(db, features)

    assert usgs.normalize_to_events(db) == len(features)

    for feature in features:
        event = db.get(Event, ("usgs", feature["id"]))
        assert event.peril == "earthquake"
        if feature["properties"]["alert"] is None:
            assert event.humanitarian_score is None
            assert event.confidence == "no PAGER product available"
        else:
            raw = db.get(RawUsgsEvent, feature["id"])
            expected = scoring.humanitarian_score(
                usgs._weighted_population_exposure(raw.pager_population_exposure)
            )
            assert event.humanitarian_score == expected
            assert event.overall_score == scoring.overall_score(expected, None)
