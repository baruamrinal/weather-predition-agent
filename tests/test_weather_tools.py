"""Tests pinning the existing Open-Meteo helpers (TASKS T2.1-T2.4)."""

from datetime import date

import pytest

from weather_agent.tools import weather as wt


# --- T2.1 geocode / forecast ---------------------------------------------------------


def test_geocode_returns_location_fields(fake_api):
    fake_api.respond(
        wt.GEOCODE_URL,
        {
            "results": [
                {
                    "name": "Paris",
                    "admin1": "Île-de-France",
                    "country": "France",
                    "latitude": 48.85,
                    "longitude": 2.35,
                    "timezone": "Europe/Paris",
                    "population": 2_000_000,
                }
            ]
        },
    )
    assert wt.geocode("Paris") == [
        {
            "name": "Paris",
            "admin1": "Île-de-France",
            "country": "France",
            "latitude": 48.85,
            "longitude": 2.35,
            "timezone": "Europe/Paris",
        }
    ]


def test_geocode_returns_empty_list_when_no_match(fake_api):
    fake_api.respond(wt.GEOCODE_URL, {"generationtime_ms": 0.1})
    assert wt.geocode("Nowhereville") == []


def _daily_payload(days: int) -> dict:
    daily = {"time": [f"2026-11-0{i + 1}" for i in range(days)]}
    for field in wt.DAILY_FIELDS:
        daily[field] = [3 if field == "weather_code" else i for i in range(days)]
    return {
        "timezone": "Asia/Kolkata",
        "daily": daily,
        "daily_units": {},
        "current": {"temperature_2m": 30.0, "weather_code": 61},
        "current_units": {},
    }


def test_forecast_one_row_per_day_with_readable_conditions(fake_api):
    fake_api.respond(wt.FORECAST_URL, _daily_payload(3))
    result = wt.forecast(22.5, 88.3, days=3)
    assert [row["date"] for row in result["daily"]] == ["2026-11-01", "2026-11-02", "2026-11-03"]
    assert all(row["conditions"] == "Overcast" for row in result["daily"])
    assert "weather_code" not in result["daily"][0]
    assert result["current"]["conditions"] == "Slight rain"


@pytest.mark.parametrize("requested, sent", [(0, 1), (7, 7), (40, 16)])
def test_forecast_clamps_days(fake_api, requested, sent):
    fake_api.respond(wt.FORECAST_URL, _daily_payload(1))
    wt.forecast(0, 0, days=requested)
    assert fake_api.last_params(wt.FORECAST_URL)["forecast_days"] == sent


def test_forecast_passes_temperature_unit(fake_api):
    fake_api.respond(wt.FORECAST_URL, _daily_payload(1))
    wt.forecast(0, 0, unit="fahrenheit")
    assert fake_api.last_params(wt.FORECAST_URL)["temperature_unit"] == "fahrenheit"


# --- T2.2 hourly_forecast ------------------------------------------------------------


def test_hourly_forecast_one_row_per_hour(fake_api):
    hours = [f"2026-11-01T{h:02d}:00" for h in range(24)]
    hourly = {"time": hours}
    for field in wt.HOURLY_FIELDS:
        hourly[field] = [95 if field == "weather_code" else 1 for _ in hours]
    fake_api.respond(wt.FORECAST_URL, {"timezone": "UTC", "hourly": hourly, "hourly_units": {}})

    result = wt.hourly_forecast(0, 0, "2026-11-01", "2026-11-01")
    assert len(result["hourly"]) == 24
    assert result["hourly"][0]["time"] == "2026-11-01T00:00"
    assert result["hourly"][0]["conditions"] == "Thunderstorm"


def test_hourly_forecast_rejects_reversed_dates(fake_api):
    with pytest.raises(ValueError):
        wt.hourly_forecast(0, 0, "2026-11-02", "2026-11-01")


def test_hourly_forecast_rejects_more_than_three_days(fake_api):
    with pytest.raises(ValueError):
        wt.hourly_forecast(0, 0, "2026-11-01", "2026-11-04")


# --- T2.3 air_quality ----------------------------------------------------------------


def _aq_payload(aqi_by_hour: list, day: str = "2026-11-01") -> dict:
    times = [f"{day}T{h:02d}:00" for h in range(len(aqi_by_hour))]
    return {
        "timezone": "UTC",
        "current": {"us_aqi": 42, "pm2_5": 10.0, "pm10": 20.0},
        "hourly": {"time": times, "us_aqi": aqi_by_hour, "pm2_5": [10.0] * len(times), "pm10": [20.0] * len(times)},
    }


def test_air_quality_daily_max_mean_and_worst_hour(fake_api):
    fake_api.respond(wt.AIR_QUALITY_URL, _aq_payload([40, 160, 100, 20]))
    result = wt.air_quality(0, 0, days=1)
    day = result["daily"][0]
    assert day["date"] == "2026-11-01"
    assert day["us_aqi_max"] == 160
    assert day["us_aqi_mean"] == 80
    assert day["worst_hour"] == "01:00"
    assert day["category_at_worst"] == "Unhealthy"
    assert result["current"]["category"] == "Good"


@pytest.mark.parametrize(
    "aqi, label",
    [(50, "Good"), (51, "Moderate"), (101, "Unhealthy for sensitive groups"), (201, "Very unhealthy"), (301, "Hazardous")],
)
def test_aqi_categories(aqi, label):
    assert wt._aqi_category(aqi) == label


def test_air_quality_skips_missing_hours(fake_api):
    fake_api.respond(wt.AIR_QUALITY_URL, _aq_payload([None, 60, None]))
    day = wt.air_quality(0, 0, days=1)["daily"][0]
    assert day["us_aqi_max"] == 60
    assert day["us_aqi_mean"] == 60


# --- T2.4 climate_normals ------------------------------------------------------------


def _archive_payload(rows: list[tuple[str, float, float, float]]) -> dict:
    return {
        "daily": {
            "time": [r[0] for r in rows],
            "temperature_2m_max": [r[1] for r in rows],
            "temperature_2m_min": [r[2] for r in rows],
            "precipitation_sum": [r[3] for r in rows],
        }
    }


def test_climate_normals_uses_only_matching_calendar_days(fake_api):
    fake_api.respond(
        wt.ARCHIVE_URL,
        _archive_payload(
            [
                ("2024-10-31", 99.0, 99.0, 99.0),  # outside window
                ("2024-11-01", 30.0, 20.0, 0.0),
                ("2024-11-02", 32.0, 22.0, 5.0),
                ("2025-11-01", 28.0, 18.0, 0.5),
                ("2025-11-02", 30.0, 24.0, 10.0),
                ("2025-11-03", 99.0, 99.0, 99.0),  # outside window
            ]
        ),
    )
    result = wt.climate_normals(0, 0, "2026-11-01", "2026-11-02", years=2)
    assert result["avg_high"] == 30.0
    assert result["avg_low"] == 21.0
    assert result["avg_daily_precipitation"] == 3.9
    assert result["share_of_rainy_days"] == "50%"
    assert result["record_high"] == {"value": 32.0, "date": "2024-11-02"}
    assert result["record_low"] == {"value": 18.0, "date": "2025-11-01"}
    assert result["wettest_day"] == {"value": 10.0, "date": "2025-11-02"}
    assert result["years_covered"] == ["2024", "2025"]


def test_climate_normals_window_across_new_year(fake_api, monkeypatch):
    fake_api.respond(
        wt.ARCHIVE_URL,
        _archive_payload(
            [
                ("2024-12-30", 10.0, 0.0, 0.0),
                ("2024-12-31", 12.0, 2.0, 0.0),
                ("2025-01-01", 14.0, 4.0, 0.0),
                ("2025-01-02", 16.0, 6.0, 0.0),
                ("2025-01-03", 99.0, 99.0, 0.0),  # outside window
            ]
        ),
    )
    result = wt.climate_normals(0, 0, "2025-12-30", "2026-01-02", years=1)
    assert result["avg_high"] == 13.0
    assert result["record_high"]["value"] == 16.0


def test_climate_normals_rejects_long_window(fake_api):
    with pytest.raises(ValueError):
        wt.climate_normals(0, 0, "2026-01-01", "2026-03-01")


def test_climate_normals_never_requests_recent_days(fake_api):
    fake_api.respond(wt.ARCHIVE_URL, _archive_payload([("2025-11-01", 1.0, 1.0, 1.0)]))
    wt.climate_normals(0, 0, "2026-11-01", "2026-11-01", years=1)
    end = date.fromisoformat(fake_api.last_params(wt.ARCHIVE_URL)["end_date"])
    assert end <= date.today()
