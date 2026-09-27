"""Device simulator (Phase 9). Produces readings labelled "Simulated device" from live or synthetic weather.

`step()` is pure so the same model drives the in-app scheduler job and scripts/device_simulator.py.
A real ESP32 posting to /api/iot/readings replaces this without any change to the app.
"""
import math
import random
from datetime import datetime, timedelta

from ..extensions import db
from ..models import Device
from ..models.core import utcnow
from .config_loader import iot as iot_config
from .config_loader import thresholds
from .iot import SENSOR_KIND, ingest
from .weather import get_forecast


def synthetic_weather(local_dt):
    """Fallback diurnal pattern when no forecast is available (clearly not observed weather)."""
    h = local_dt.hour + local_dt.minute / 60
    phase = math.sin(2 * math.pi * (h - 9) / 24)
    rain = 2.0 if 15 <= h < 17 else 0.0
    return {"temp": round(27 + 5 * phase, 1), "rh": round(min(98, 80 - 16 * phase + (10 if rain else 0)), 1),
            "rain": rain}


def weather_lookup(series):
    """Map 'YYYY-MM-DDTHH:00' (MYT) -> hourly weather from an Open-Meteo series."""
    if not series:
        return {}
    return {t[:13]: {"temp": series["temp"][i], "rh": series["rh"][i], "rain": series["rain"][i]}
            for i, t in enumerate(series["time"])
            if series["temp"][i] is not None and series["rh"][i] is not None}


def weather_at(lookup, ts_utc):
    local = ts_utc.replace(tzinfo=None) + timedelta(hours=8)
    w = lookup.get(local.strftime("%Y-%m-%dT%H"))
    if w:
        return {**w, "rain": w["rain"] or 0.0}, local
    return synthetic_weather(local), local


def initial_state(cfg=None):
    cfg = cfg or iot_config()["simulator"]
    init = cfg["initial"]
    return {"soil_moisture_pct": init["soil_moisture_pct"], "soil_ec_ds_m": init["soil_ec_ds_m"],
            "battery_pct": init["battery_pct"], "soil_temp_c": 27.0}


def step(state, weather, local_dt, dt_hours, cfg, leaf_wet_rh, rain_threshold, rng, water_mm=0.0):
    """Advance the soil/air model by dt_hours. Returns (new_state, reading)."""
    pct_per_mm = 100 / cfg["root_zone_mm"]
    h = local_dt.hour + local_dt.minute / 60
    sun = max(0.0, math.sin(math.pi * (h - 7) / 12)) if 7 <= h <= 19 else 0.0
    rain = weather["rain"] or 0.0
    cloud = 0.35 if rain >= rain_threshold else 1.0

    vpd_factor = max(0.0, (weather["temp"] - 10) / 20) * max(0.0, (100 - weather["rh"]) / 40)
    et = cfg["et_mm_per_hour_peak"] * sun * cloud * vpd_factor * dt_hours
    m = state["soil_moisture_pct"]
    m += (rain * cfg["rain_infiltration"] * dt_hours + water_mm) * pct_per_mm
    m -= et * pct_per_mm * (1.0 if m > cfg["wilting_pct"] else 0.2)
    if m > cfg["field_capacity_pct"]:
        m -= (m - cfg["field_capacity_pct"]) * min(1.0, cfg["drainage_per_hour"] * dt_hours)
    m = min(cfg["saturation_pct"], max(cfg["wilting_pct"] * 0.6, m))

    ec = max(0.1, state["soil_ec_ds_m"] - cfg["ec_decay_per_hour"] * dt_hours - 0.01 * rain * dt_hours)
    soil_t = state["soil_temp_c"] + (weather["temp"] - 1.5 - state["soil_temp_c"]) * min(1.0, 0.3 * dt_hours)
    batt = max(5.0, state["battery_pct"] - 0.01 * dt_hours + (0.05 * sun * dt_hours if sun > 0.3 else 0))
    batt = min(100.0, batt)

    new = {"soil_moisture_pct": m, "soil_ec_ds_m": ec, "soil_temp_c": soil_t, "battery_pct": batt}
    reading = {
        "soil_moisture_pct": round(m + rng.gauss(0, 0.4), 1),
        "soil_temp_c": round(soil_t + rng.gauss(0, 0.2), 1),
        "air_temp_c": round(weather["temp"] + rng.gauss(0, 0.3), 1),
        "air_rh_pct": round(min(100.0, max(0.0, weather["rh"] + rng.gauss(0, 1.0))), 1),
        "soil_ec_ds_m": round(max(0.0, ec + rng.gauss(0, 0.03)), 2),
        "light_lux": round(max(0.0, 90000 * sun * cloud * (1 + rng.gauss(0, 0.05)))),
        "battery_pct": round(batt, 1),
        "leaf_wet": bool(weather["rh"] >= leaf_wet_rh or rain >= rain_threshold),
    }
    return new, reading


def _floor(ts, minutes):
    return ts.replace(minute=(ts.minute // minutes) * minutes, second=0, microsecond=0)


def simulate_device(device, now=None, backfill_hours=None):
    """Generate readings for a simulated device from its last simulated time up to now. Returns count."""
    cfg_all = iot_config()
    cfg = cfg_all["simulator"]
    wcfg = thresholds()["weather"]
    interval = timedelta(minutes=cfg["interval_minutes"])
    now = _floor(now or utcnow(), cfg["interval_minutes"])
    state = dict(device.sim_state or {})
    earliest = now - timedelta(hours=backfill_hours or cfg["initial_backfill_hours"])
    last = datetime.fromisoformat(state["ts"]) if state.get("ts") else None
    if last is None or last < earliest - interval:
        last = earliest - interval
        state = {**initial_state(cfg), **{k: v for k, v in state.items() if k == "ts"}}
    if not {"soil_moisture_pct", "soil_ec_ds_m", "soil_temp_c", "battery_pct"} <= state.keys():
        state = {**initial_state(cfg), **state}
    lookup = weather_lookup(get_forecast(device.plot.lat, device.plot.lon))
    payloads = []
    ts = last + interval
    while ts <= now:
        weather, local = weather_at(lookup, ts)
        rng = random.Random(f"{device.uid}|{ts.isoformat()}")
        model, reading = step(state, weather, local, interval.total_seconds() / 3600, cfg,
                              wcfg["leaf_wetness_rh"], wcfg["rain_mm_threshold"], rng)
        state.update(model)
        payloads.append({**reading, "ts": ts.isoformat() + "+00:00"})
        ts += interval
    if not payloads:
        return 0
    batch = cfg_all["max_batch"]
    for i in range(0, len(payloads), batch):
        ingest(device, payloads[i:i + batch], now=now, transport="sim")
    state["ts"] = (ts - interval).isoformat()
    device.sim_state = state
    db.session.commit()
    return len(payloads)


def run_simulated_devices(now=None):
    """Advance every simulated device. Returns {uid: readings_added}."""
    devices = Device.query.filter(Device.is_simulated.is_(True), Device.kind == SENSOR_KIND).all()
    return {d.uid: simulate_device(d, now=now) for d in devices}

