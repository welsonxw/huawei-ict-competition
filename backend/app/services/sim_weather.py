"""Deterministic simulated weather for the demo scenario (a rainy spell building up to today and beyond).

Only used for simulated scans. Anything computed from it is flagged simulated and labelled
"Simulated scenario" in the UI.
"""
import hashlib
import math
from datetime import datetime, timedelta

from .config_loader import demo_scenario
from .weather import FORECAST_DAYS, PAST_DAYS


def wetness(day_offset, cell):
    w = demo_scenario()["weather"]
    jitter = (int(hashlib.sha1(cell.encode()).hexdigest()[:4], 16) / 0xFFFF - 0.5) * 0.1
    base = w["wet_start"] + w["wet_per_day"] * max(0, day_offset + 3)
    return min(1.0, max(0.0, base + jitter))


def series(cell, today):
    """Hourly series from PAST_DAYS before `today` (a date) to FORECAST_DAYS after, like Open-Meteo."""
    start = datetime.combine(today, datetime.min.time()) - timedelta(days=PAST_DAYS)
    out = {"time": [], "temp": [], "rh": [], "rain": [], "cell": cell, "simulated": True}
    for d in range(PAST_DAYS + FORECAST_DAYS):
        wet = wetness(d - PAST_DAYS, cell)
        rain_hours = set(range(14, 14 + round(6 * wet)))
        for hr in range(24):
            night = hr < 8 or hr >= 20
            out["time"].append((start + timedelta(days=d, hours=hr)).isoformat(timespec="minutes"))
            out["temp"].append(round(25 + 4 * math.sin(math.pi * (hr - 9) / 12) - 2 * wet, 1))
            out["rh"].append(round((70 + 25 * wet) if night else (60 + 30 * wet), 1))
            out["rain"].append(2.0 if hr in rain_hours else 0.0)
    return out
