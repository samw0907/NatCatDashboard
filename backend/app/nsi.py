# backend/app/nsi.py

from typing import Any

import httpx
from shapely.geometry import Point, shape

NSI_URL = "https://nsi.sec.usace.army.mil/nsiapi/structures"


def _structure_population(props: dict) -> float:
    """NSI gives day/night population separately (pop2am*/pop2pm*) - O6
    (2026-08-23) resolved to use a single figure rather than switching by
    time of day. PM (daytime) chosen as the default: it captures
    workplace/ambient population alongside residential, closer to the
    "ambient population" concept the plan favoured generally (section
    5.5) than a purely residential (AM) count. Not a perfect fit for every
    event's actual time of occurrence - a stated simplification, not a
    hidden one."""
    return (props.get("pop2pmo65") or 0) + (props.get("pop2pmu65") or 0)


def _structure_value(props: dict) -> float:
    return (props.get("val_struct") or 0) + (props.get("val_cont") or 0)


def fetch_structures_in_footprint(footprint_geojson: dict) -> list[dict]:
    """Two-step query: a cheap bounding-box request to NSI's API, then a
    precise point-in-polygon filter locally via shapely against the real
    footprint. Sending a complex multi-thousand-point perimeter directly as
    NSI's polygon-ring bbox parameter isn't practical - Phase 0 saw real
    wildfire perimeters with 3,000+ coordinate points, and NSI's documented
    bbox format is a simple closed ring, not built for that."""
    geom = shape(footprint_geojson)
    minx, miny, maxx, maxy = geom.bounds
    ring = f"{minx},{miny},{minx},{maxy},{maxx},{maxy},{maxx},{miny},{minx},{miny}"

    resp = httpx.get(NSI_URL, params={"bbox": ring}, timeout=60)
    resp.raise_for_status()
    features = resp.json().get("features", [])

    matched = []
    for feature in features:
        props = feature.get("properties", {})
        x, y = props.get("x"), props.get("y")
        if x is None or y is None:
            continue
        if geom.contains(Point(x, y)):
            matched.append(props)
    return matched


def summarize_exposure(footprint_geojson: dict | None) -> dict[str, Any]:
    """Population exposed and total replacement cost (structure + content
    value) for structures within the footprint. All None if no footprint
    is available yet for this event."""
    if not footprint_geojson:
        return {"population_exposed": None, "replacement_cost_usd": None, "structure_count": None}

    structures = fetch_structures_in_footprint(footprint_geojson)
    return {
        "population_exposed": sum(_structure_population(s) for s in structures),
        "replacement_cost_usd": sum(_structure_value(s) for s in structures),
        "structure_count": len(structures),
    }
