# backend/tests/test_gdacs_nsi.py

from shapely.geometry import Point, box

from app import gdacs, nsi
from app.models import Event, RawGdacsEvent

from .conftest import load_json


def test_gdacs_is_stored_raw_and_never_normalised(db):
    features = load_json("gdacs_search.json")["features"]

    result = gdacs.upsert_events(db, features)

    assert result["fetched"] == len(features)
    assert db.query(RawGdacsEvent).count() == len(features)
    assert db.query(Event).count() == 0
    first = gdacs.parse_feature(features[0])
    assert first["severity_unit"] == features[0]["properties"]["severitydata"]["severityunit"]


def _structures():
    return [f["properties"] for f in load_json("nsi_structures.json")["features"]]


def test_nsi_query_uses_a_closed_ring_bbox(fake_http):
    fake = fake_http({"nsiapi/structures": "nsi_structures.json"})
    footprint = box(-101.8, 41.5, -101.6, 41.7).__geo_interface__

    nsi.fetch_structures_in_footprint(footprint)

    _, params = fake.calls[0]
    coords = [float(v) for v in params["bbox"].split(",")]
    assert len(coords) == 10
    assert coords[:2] == coords[-2:]


def test_nsi_point_in_polygon_matches_an_independent_count(fake_http):
    fake_http({"nsiapi/structures": "nsi_structures.json"})
    structures = _structures()
    xs = sorted(s["x"] for s in structures)
    # A footprint covering roughly the western half of the sample points.
    footprint_geom = box(xs[0] - 0.01, -90, xs[len(xs) // 2], 90)
    inside = [s for s in structures if footprint_geom.contains(Point(s["x"], s["y"]))]

    summary = nsi.summarize_exposure(footprint_geom.__geo_interface__)

    assert 0 < summary["structure_count"] == len(inside) < len(structures)
    assert summary["replacement_cost_usd"] == sum(
        (s["val_struct"] or 0) + (s["val_cont"] or 0) for s in inside
    )
    assert summary["population_exposed"] == sum(
        (s["pop2pmo65"] or 0) + (s["pop2pmu65"] or 0) for s in inside
    )


def test_nsi_without_footprint_returns_nones():
    assert nsi.summarize_exposure(None) == {
        "population_exposed": None,
        "replacement_cost_usd": None,
        "structure_count": None,
    }
