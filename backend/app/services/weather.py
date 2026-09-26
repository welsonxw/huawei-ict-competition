"""Open-Meteo hourly forecast, cached in Redis (Huawei Cloud DCS in production)."""
import json
import logging
from datetime import datetime, timedelta, timezone

import requests

from ..extensions import cache
from .config_loader import thresholds
from .grid import cell_center, cell_id

log = logging.getLogger(__name__)

MYT = timezone(timedelta(hours=8))

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = "temperature_2m,relative_humidity_2m,precipitation"


def _cache_key(cid):
    return f"weather:{cid}"


def fetch_open_meteo(lat, lon, forecast_days=7, past_days=0):
    res = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "hourly": HOURLY_VARS,
            "forecast_days": forecast_days,
            "past_days": past_days,
            "timezone": "Asia/Kuala_Lumpur",
        },
        timeout=15,
    )
    res.raise_for_status()
    h = res.json()["hourly"]
    return {
        "time": h["time"],
        "temp": h["temperature_2m"],
        "rh": h["relative_humidity_2m"],
        "rain": h["precipitation"],
    }


def get_forecast_for_cell(cid, refresh=False):
    """Return cached hourly forecast for a grid cell, fetching it if missing. None if unavailable."""
    cfg = thresholds()
    key = _cache_key(cid)
    if not refresh:
        cached = cache.client.get(key)
        if cached:
            return json.loads(cached)
    lat, lon = cell_center(cid, cfg["grid"]["cell_deg"])
    try:
        data = fetch_open_meteo(lat, lon)
    except (requests.RequestException, KeyError, ValueError) as exc:
        log.warning("weather fetch failed for %s: %s", cid, exc)
        return None
    data["cell"] = cid
    cache.client.set(key, json.dumps(data), ex=cfg["weather"]["cache_ttl_seconds"])
    return data


def get_forecast(lat, lon, refresh=False):
    return get_forecast_for_cell(cell_id(lat, lon, thresholds()["grid"]["cell_deg"]), refresh=refresh)


def now_local():
    return datetime.now(MYT).replace(tzinfo=None)


def start_index(times, now=None):
    """Index of the current hour in an Open-Meteo hourly series (which starts at local midnight)."""
    now = (now or now_local()).replace(minute=0, second=0, microsecond=0)
    for i, t in enumerate(times):
        if datetime.fromisoformat(t) >= now:
            return i
    return len(times)


def summarise(forecast, hours, rain_mm, wet_rh, now=None):
    """Summarise the next `hours` of an hourly forecast, starting from the current local hour."""
    if not forecast:
        return None
    now = now or now_local()
    i0 = start_index(forecast["time"], now)
    sl = slice(i0, i0 + hours)
    times, rain, rh, temp = forecast["time"][sl], forecast["rain"][sl], forecast["rh"][sl], forecast["temp"][sl]
    if not times:
        return None
    rain_idx = [i for i, r in enumerate(rain) if r is not None and r >= rain_mm]
    first = rain_idx[0] if rain_idx else None
    rain_when = None
    if first is not None:
        days_ahead = (datetime.fromisoformat(times[first]).date() - now.date()).days
        rain_when = "soon" if first < 6 else "today" if days_ahead == 0 else "tomorrow" if days_ahead == 1 else "later"
    return {
        "hours": len(times),
        "rain_hours": len(rain_idx),
        "total_rain_mm": round(sum(r or 0 for r in rain), 1),
        "first_rain_hour": first,
        "first_rain_time": times[first] if first is not None else None,
        "rain_when": rain_when,
        "wet_hours": sum(1 for x in rh if x is not None and x >= wet_rh),
        "max_temp": max((t for t in temp if t is not None), default=None),
        "min_temp": min((t for t in temp if t is not None), default=None),
    }
