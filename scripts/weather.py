#!/usr/bin/env python3
"""Fetch weather data from weather.gov for Austin, TX.

Reuses logic from bourov.github.io/scripts/generate_daily_briefing.py.
"""

import sys
from datetime import datetime, timedelta, timezone

import requests

LATITUDE = 30.4015
LONGITUDE = -97.7254
NWS_USER_AGENT = "(bourov.github.io daily-briefing, github-actions)"
HEADERS = {"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"}


def fetch_weather() -> dict | None:
    """Fetch current weather and forecast for Austin, TX from weather.gov."""
    try:
        point = requests.get(
            f"https://api.weather.gov/points/{LATITUDE},{LONGITUDE}",
            headers=HEADERS,
            timeout=15,
        )
        point.raise_for_status()
        props = point.json()["properties"]

        forecast = requests.get(props["forecast"], headers=HEADERS, timeout=15)
        forecast.raise_for_status()
        periods = forecast.json()["properties"]["periods"]

        stations = requests.get(props["observationStations"], headers=HEADERS, timeout=15)
        stations.raise_for_status()
        station_id = stations.json()["features"][0]["properties"]["stationIdentifier"]

        obs = requests.get(
            f"https://api.weather.gov/stations/{station_id}/observations/latest",
            headers=HEADERS,
            timeout=15,
        )
        obs.raise_for_status()
        observation = obs.json()["properties"]

        return {
            "forecast_periods": periods[:6],
            "current_observation": {
                "temperature_c": observation.get("temperature", {}).get("value"),
                "humidity": observation.get("relativeHumidity", {}).get("value"),
                "wind_speed_kmh": observation.get("windSpeed", {}).get("value"),
                "wind_direction": observation.get("windDirection", {}).get("value"),
                "description": observation.get("textDescription"),
            },
        }
    except Exception as exc:
        print(f"Warning: weather fetch failed: {exc}", file=sys.stderr)
        return None


def format_weather(weather_data: dict | None, austin_date: str) -> dict:
    """Convert raw weather data into display-ready dict for the HTML template."""
    if not weather_data:
        return {"available": False}

    obs = weather_data["current_observation"]
    periods = weather_data["forecast_periods"]

    temp_c = obs.get("temperature_c")
    if temp_c is not None:
        temp_f = round(temp_c * 9 / 5 + 32)
        temp_c = round(temp_c)
    else:
        temp_f = None

    humidity = obs.get("humidity")
    if humidity is not None:
        humidity = round(humidity)

    wind_kmh = obs.get("wind_speed_kmh")
    wind_dir = obs.get("wind_direction")
    if wind_kmh is not None:
        wind_mph = round(wind_kmh * 0.621371, 1)
        wind_dir_str = _degrees_to_cardinal(wind_dir) if wind_dir else ""
        wind_str = f"{wind_kmh:.1f} km/h ({wind_mph} mph) {wind_dir_str}".strip()
    else:
        wind_str = "N/A"

    conditions = obs.get("description", "N/A")

    tonight_low = None
    tomorrow_high = None
    tonight_conditions = ""
    tomorrow_conditions = ""
    precip_parts = []

    for p in periods:
        name = p.get("name", "").lower()
        temp = p.get("temperature")
        pop = p.get("probabilityOfPrecipitation", {}).get("value")
        short = p.get("shortForecast", "")
        if "tonight" in name or "night" in name:
            if tonight_low is None:
                tonight_low = temp
                tonight_conditions = short
                if pop is not None:
                    precip_parts.append(f"{pop}% tonight")
        elif tomorrow_high is None and not p.get("isDaytime", True) is False:
            if p.get("isDaytime", True) and tonight_low is not None:
                tomorrow_high = temp
                tomorrow_conditions = short
                if pop is not None:
                    precip_parts.append(f"{pop}% tomorrow")
        if pop is not None and not precip_parts:
            precip_parts.append(f"{pop}% today")

    if periods and not precip_parts:
        pop = periods[0].get("probabilityOfPrecipitation", {}).get("value")
        if pop is not None:
            precip_parts.append(f"{pop}%")

    tonight_f = tonight_low
    tonight_c = round((tonight_low - 32) * 5 / 9) if tonight_low else None
    tomorrow_f = tomorrow_high
    tomorrow_c = round((tomorrow_high - 32) * 5 / 9) if tomorrow_high else None

    return {
        "available": True,
        "temp_c": temp_c,
        "temp_f": temp_f,
        "humidity": humidity,
        "wind": wind_str,
        "conditions": conditions,
        "tonight_low_f": tonight_f,
        "tonight_low_c": tonight_c,
        "tonight_conditions": tonight_conditions,
        "tomorrow_high_f": tomorrow_f,
        "tomorrow_high_c": tomorrow_c,
        "tomorrow_conditions": tomorrow_conditions,
        "precip": " · ".join(precip_parts) if precip_parts else "0%",
        "source_date": austin_date,
    }


def _degrees_to_cardinal(deg: float | None) -> str:
    if deg is None:
        return ""
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                   "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(deg / 22.5) % 16
    return directions[idx]
