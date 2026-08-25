# backend/app/scoring.py

import math

# GDACS's own wildfire homepage-display threshold uses "population within
# 5km exceeding 10,000" as one of two criteria (plan section 5.4, verified
# Phase 0) - the only real published "this matters" population-exposure
# reference point found during research. Generalised here across perils as
# the humanitarian axis's score=50 anchor. There's no equivalent specific
# to earthquake or wind, so this is a stated assumption, not a perfect fit
# borrowed from an identical context - worth revisiting if a better anchor
# turns up.
HUMANITARIAN_REFERENCE_POPULATION = 10_000

# PCS's real, published US catastrophe-designation threshold (plan section
# 4.1) - the economic axis's score=50 anchor.
ECONOMIC_REFERENCE_USD = 25_000_000


def _log_score(value: float | None, reference: float) -> float | None:
    """Continuous log-scale score, not banded (Phase 3 design decision,
    2026-08-25) - avoids clumping many real events into the same tier the
    way Phase 1(d)'s PAGER-band placeholder did (all 4 live earthquakes
    scored identically at the time). value == reference maps to 50; two
    orders of magnitude above maps to 100; two orders of magnitude below
    maps to 0."""
    if value is None or value <= 0:
        return None
    score = 50 + 25 * math.log10(value / reference)
    return max(0.0, min(100.0, score))


def humanitarian_score(population_exposed: float | None) -> float | None:
    return _log_score(population_exposed, HUMANITARIAN_REFERENCE_POPULATION)


def economic_score(replacement_cost_usd: float | None) -> float | None:
    return _log_score(replacement_cost_usd, ECONOMIC_REFERENCE_USD)


def overall_score(humanitarian: float | None, economic: float | None) -> float | None:
    """Max rule (plan D11, section 6.2) - an event severe on either axis
    ranks accordingly; moderate-on-both doesn't inflate."""
    present = [s for s in (humanitarian, economic) if s is not None]
    return max(present) if present else None
