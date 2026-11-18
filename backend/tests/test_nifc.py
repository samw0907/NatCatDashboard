# backend/tests/test_nifc.py

from datetime import datetime, timezone

from shapely.geometry import shape

from app import nifc
from app.models import Event

from .conftest import load_json


def test_upsert_and_normalize_give_each_fire_a_real_footprint(db):
    features = load_json("nifc_perimeters.json")["features"]

    assert nifc.upsert_events(db, features) == {"fetched": len(features), "skipped_no_id": 0}
    assert nifc.normalize_to_events(db) == len(features)

    for feature in features:
        event = db.get(Event, ("nifc", feature["properties"]["attr_IrwinID"]))
        assert event.peril == "wildfire"
        assert event.footprint_geojson == feature["geometry"]
        centroid = shape(feature["geometry"]).centroid
        assert (event.longitude, event.latitude) == (centroid.x, centroid.y)
        assert event.primary_metric_value == feature["properties"]["poly_GISAcres"]
        assert event.confidence == "not yet scored"


def test_feature_without_irwin_id_is_skipped_and_counted(db):
    feature = load_json("nifc_perimeters.json")["features"][0]
    feature["properties"]["attr_IrwinID"] = None
    assert nifc.upsert_events(db, [feature]) == {"fetched": 0, "skipped_no_id": 1}


def test_normalize_preserves_existing_scores(db):
    feature = load_json("nifc_perimeters.json")["features"][0]
    nifc.upsert_events(db, [feature])
    nifc.normalize_to_events(db)
    event = db.get(Event, ("nifc", feature["properties"]["attr_IrwinID"]))
    event.humanitarian_score, event.economic_score, event.overall_score = 10.0, 60.0, 60.0
    event.scored_at = datetime.now(timezone.utc)
    db.commit()

    nifc.normalize_to_events(db)

    event = db.get(Event, ("nifc", feature["properties"]["attr_IrwinID"]))
    assert (event.humanitarian_score, event.economic_score, event.overall_score) == (10.0, 60.0, 60.0)


def test_score_limit_zero_scores_nothing(db):
    nifc.upsert_events(db, load_json("nifc_perimeters.json")["features"])
    nifc.normalize_to_events(db)
    result = nifc.score_events(db, limit=0)
    assert result["scored"] == 0
    assert result["remaining"] == 2
