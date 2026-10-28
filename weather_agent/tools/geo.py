"""Geographic helpers: distances are computed locally, elevation comes from Open-Meteo."""

import math

from weather_agent.tools import http

ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

EARTH_RADIUS_KM = 6371.0
# Rough conversion from straight-line to road distance and an average road speed.
# Labelled as an estimate in every result; real routing is T4.1.
ROAD_FACTOR = 1.3
AVG_ROAD_SPEED_KMH = 50


def distance(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Great-circle distance between two points, plus a rough road distance and drive time."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    straight_km = 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
    road_km = straight_km * ROAD_FACTOR
    return {
        "straight_line_km": round(straight_km, 1),
        "estimated_road_km": round(road_km, 1),
        "estimated_drive_hours": round(road_km / AVG_ROAD_SPEED_KMH, 1),
        "method": "estimate",
    }


def elevation(latitude: float, longitude: float) -> dict:
    """Elevation of a point in metres."""
    data = http.get_json(ELEVATION_URL, {"latitude": latitude, "longitude": longitude})
    values = data.get("elevation") or []
    if not values or values[0] is None:
        raise ValueError("no elevation data for this point")
    return {"latitude": latitude, "longitude": longitude, "elevation_m": values[0]}
