"""TASKS T2.5 (distance) and T2.6 (elevation)."""

import pytest

from weather_agent.tools import geo

LONDON = (51.5074, -0.1278)
PARIS = (48.8566, 2.3522)


# --- T2.5 distance -------------------------------------------------------------------


def test_distance_london_paris_within_one_percent():
    result = geo.distance(*LONDON, *PARIS)
    assert result["straight_line_km"] == pytest.approx(344, rel=0.01)


def test_distance_to_same_point_is_zero():
    result = geo.distance(*PARIS, *PARIS)
    assert result["straight_line_km"] == 0
    assert result["estimated_drive_hours"] == 0


def test_distance_includes_labelled_road_estimate():
    result = geo.distance(*LONDON, *PARIS)
    assert result["estimated_road_km"] == pytest.approx(result["straight_line_km"] * 1.3, abs=0.1)
    assert result["estimated_drive_hours"] == pytest.approx(result["estimated_road_km"] / 50, abs=0.1)
    assert result["method"] == "estimate"


# --- T2.6 elevation ------------------------------------------------------------------


def test_elevation_returns_metres(fake_api):
    fake_api.respond(geo.ELEVATION_URL, {"elevation": [2134.0]})
    assert geo.elevation(27.04, 88.26) == {"latitude": 27.04, "longitude": 88.26, "elevation_m": 2134.0}
    assert fake_api.last_params(geo.ELEVATION_URL) == {"latitude": 27.04, "longitude": 88.26}


def test_elevation_missing_value_raises(fake_api):
    fake_api.respond(geo.ELEVATION_URL, {"elevation": []})
    with pytest.raises(ValueError):
        geo.elevation(0, 0)
