# backend/tests/test_scoring.py

import pytest

from app import scoring


def test_reference_values_score_fifty():
    assert scoring.humanitarian_score(scoring.HUMANITARIAN_REFERENCE_POPULATION) == pytest.approx(50)
    assert scoring.economic_score(scoring.ECONOMIC_REFERENCE_USD) == pytest.approx(50)


def test_two_orders_of_magnitude_span_the_scale():
    ref = scoring.HUMANITARIAN_REFERENCE_POPULATION
    assert scoring.humanitarian_score(ref * 100) == pytest.approx(100)
    assert scoring.humanitarian_score(ref / 100) == pytest.approx(0)


def test_scores_are_clamped():
    assert scoring.economic_score(scoring.ECONOMIC_REFERENCE_USD * 10_000) == 100
    assert scoring.economic_score(1) == 0


def test_missing_or_zero_exposure_is_unscored_not_zero():
    # Documented behaviour (PROGRESS.md known issues): log scale is undefined at 0.
    assert scoring.humanitarian_score(None) is None
    assert scoring.humanitarian_score(0) is None


def test_overall_is_the_max_of_the_axes():
    assert scoring.overall_score(30.0, 70.0) == 70.0
    assert scoring.overall_score(None, 40.0) == 40.0
    assert scoring.overall_score(None, None) is None
