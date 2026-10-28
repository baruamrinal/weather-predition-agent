"""Weather data tools backed by Open-Meteo (free, no API key required)."""

import statistics
from datetime import date, timedelta

from weather_agent.tools import http

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# WMO weather interpretation codes used by Open-Meteo
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

DAILY_FIELDS = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "uv_index_max",
    "sunrise",
    "sunset",
]

HOURLY_FIELDS = [
    "weather_code",
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation_probability",
    "precipitation",
    "wind_speed_10m",
    "wind_gusts_10m",
    "uv_index",
]

CURRENT_FIELDS = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "weather_code",
    "wind_speed_10m",
    "precipitation",
]


def geocode(name: str, count: int = 5) -> list[dict]:
    """Return candidate locations matching a place name."""
    data = http.get_json(GEOCODE_URL, {"name": name, "count": count, "language": "en", "format": "json"})
    return [
        {
            "name": r.get("name"),
            "admin1": r.get("admin1"),
            "country": r.get("country"),
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "timezone": r.get("timezone"),
        }
        for r in data.get("results", [])
    ]


def forecast(latitude: float, longitude: float, days: int = 7, unit: str = "celsius") -> dict:
    """Return current conditions plus a daily forecast for the given coordinates."""
    days = max(1, min(days, 16))
    data = http.get_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(DAILY_FIELDS),
            "current": ",".join(CURRENT_FIELDS),
            "timezone": "auto",
            "forecast_days": days,
            "temperature_unit": "fahrenheit" if unit == "fahrenheit" else "celsius",
            "wind_speed_unit": "kmh",
        },
    )

    daily = data["daily"]
    rows = []
    for i, date in enumerate(daily["time"]):
        row = {field: daily[field][i] for field in DAILY_FIELDS}
        row["date"] = date
        row["conditions"] = WMO_CODES.get(row.pop("weather_code"), "Unknown")
        rows.append(row)

    current = dict(data.get("current", {}))
    if "weather_code" in current:
        current["conditions"] = WMO_CODES.get(current.pop("weather_code"), "Unknown")

    return {
        "timezone": data.get("timezone"),
        "units": {"daily": data.get("daily_units"), "current": data.get("current_units")},
        "current": current,
        "daily": rows,
    }


def hourly_forecast(
    latitude: float, longitude: float, start_date: str, end_date: str, unit: str = "celsius"
) -> dict:
    """Return hour-by-hour forecast between two dates (inclusive, YYYY-MM-DD, at most 3 days)."""
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if end < start:
        raise ValueError("end_date is before start_date")
    if (end - start).days > 2:
        raise ValueError("hourly forecasts are limited to 3 days per request")

    data = http.get_json(
        FORECAST_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(HOURLY_FIELDS),
            "timezone": "auto",
            "start_date": start_date,
            "end_date": end_date,
            "temperature_unit": "fahrenheit" if unit == "fahrenheit" else "celsius",
            "wind_speed_unit": "kmh",
        },
    )

    hourly = data["hourly"]
    rows = []
    for i, time in enumerate(hourly["time"]):
        row = {field: hourly[field][i] for field in HOURLY_FIELDS}
        row["time"] = time
        row["conditions"] = WMO_CODES.get(row.pop("weather_code"), "Unknown")
        rows.append(row)

    return {"timezone": data.get("timezone"), "units": data.get("hourly_units"), "hourly": rows}


def _aqi_category(aqi: float | None) -> str:
    if aqi is None:
        return "Unknown"
    for limit, label in [
        (50, "Good"),
        (100, "Moderate"),
        (150, "Unhealthy for sensitive groups"),
        (200, "Unhealthy"),
        (300, "Very unhealthy"),
    ]:
        if aqi <= limit:
            return label
    return "Hazardous"


def air_quality(latitude: float, longitude: float, days: int = 5) -> dict:
    """Return current air quality plus a daily summary of the hourly air-quality forecast."""
    days = max(1, min(days, 7))
    data = http.get_json(
        AIR_QUALITY_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "us_aqi,pm2_5,pm10",
            "hourly": "us_aqi,pm2_5,pm10",
            "timezone": "auto",
            "forecast_days": days,
        },
    )

    hourly = data["hourly"]
    by_day: dict[str, list[int]] = {}
    for i, time in enumerate(hourly["time"]):
        by_day.setdefault(time[:10], []).append(i)

    def _values(field: str, idx: list[int]) -> list[float]:
        return [hourly[field][i] for i in idx if hourly[field][i] is not None]

    daily = []
    for day, idx in by_day.items():
        aqi = _values("us_aqi", idx)
        pm25 = _values("pm2_5", idx)
        worst = max(aqi) if aqi else None
        worst_hour = hourly["time"][idx[aqi.index(worst)]][11:] if aqi and len(aqi) == len(idx) else None
        daily.append(
            {
                "date": day,
                "us_aqi_max": worst,
                "us_aqi_mean": round(statistics.mean(aqi)) if aqi else None,
                "category_at_worst": _aqi_category(worst),
                "worst_hour": worst_hour,
                "pm2_5_mean": round(statistics.mean(pm25), 1) if pm25 else None,
            }
        )

    current = dict(data.get("current", {}))
    current["category"] = _aqi_category(current.get("us_aqi"))
    return {"timezone": data.get("timezone"), "current": current, "daily": daily}


def climate_normals(latitude: float, longitude: float, start_date: str, end_date: str, years: int = 10) -> dict:
    """Summarise observed weather for the same calendar dates over the past `years` years."""
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    if end < start or (end - start).days > 30:
        raise ValueError("date range must be in order and at most 31 days long")
    years = max(1, min(years, 30))

    window = {(start + timedelta(days=i)).strftime("%m-%d") for i in range((end - start).days + 1)}
    # The archive lags real time by a few days, so stop a week ago
    archive_end = min(date(end.year - 1, 12, 31), date.today() - timedelta(days=7))
    data = http.get_json(
        ARCHIVE_URL,
        {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": date(start.year - years, 1, 1).isoformat(),
            "end_date": archive_end.isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
        },
    )

    daily = data["daily"]
    rows = [
        (daily["time"][i], daily["temperature_2m_max"][i], daily["temperature_2m_min"][i], daily["precipitation_sum"][i])
        for i in range(len(daily["time"]))
        if daily["time"][i][5:] in window and daily["temperature_2m_max"][i] is not None
    ]
    if not rows:
        raise ValueError("no historical data available for this location and window")

    highs = [r[1] for r in rows]
    lows = [r[2] for r in rows]
    rain = [r[3] or 0.0 for r in rows]
    hottest = max(rows, key=lambda r: r[1])
    coldest = min(rows, key=lambda r: r[2])
    wettest = max(rows, key=lambda r: r[3] or 0.0)

    return {
        "window": f"{start.strftime('%b %d')} - {end.strftime('%b %d')}",
        "years_covered": sorted({r[0][:4] for r in rows}),
        "units": {"temperature": "°C", "precipitation": "mm"},
        "avg_high": round(statistics.mean(highs), 1),
        "avg_low": round(statistics.mean(lows), 1),
        "avg_daily_precipitation": round(statistics.mean(rain), 1),
        "share_of_rainy_days": f"{round(100 * sum(r >= 1.0 for r in rain) / len(rain))}%",
        "record_high": {"value": hottest[1], "date": hottest[0]},
        "record_low": {"value": coldest[2], "date": coldest[0]},
        "wettest_day": {"value": wettest[3], "date": wettest[0]},
    }
