"""Routine optimiser v1 (Phase 13): rank watering times/amounts for the next day with rules and the weather forecast.

For each candidate routine the soil-water bucket model from the device simulator is run hour by hour on the
forecast, starting from the plot's latest soil-moisture reading. Candidates are scored on:
  - time outside the crop's soil-moisture target band,
  - extra leaf-wet hours the watering itself causes (long leaf wetness drives anthracnose / early blight),
  - water used,
and anything the Phase 11 safety rules would block (rain soon, over the per-command or daily limit, wet soil)
is excluded. Fertiliser gets a timing suggestion only: rates are DOA placeholders (docs/TODO_SOURCES.md).
This is an estimate from engineering defaults, not a yield prediction.
"""
import random
from datetime import timedelta

from ..extensions import db
from ..models import ControlSchedule, Device, SensorReading
from ..models.core import utcnow
from .config_loader import iot as iot_config
from .config_loader import load_config, thresholds
from .control import (
    MYT,
    actuators,
    control_config,
    last_done,
    latest_value,
    limits,
    local_now,
    used_today,
)
from .device_sim import step, synthetic_weather, weather_lookup
from .weather import get_forecast

ESTIMATE_LABEL = "Estimate – rules + forecast, not a yield prediction"


def optimizer_config():
    return load_config("optimizer.yaml")


def hourly_weather(plot, start_local, hours):
    """Forecast weather for each local hour from start_local; falls back to a typical day when unavailable."""
    try:
        lookup = weather_lookup(get_forecast(plot.lat, plot.lon))
    except Exception:  # noqa: BLE001
        lookup = {}
    out, missing = [], 0
    for k in range(hours):
        t = start_local + timedelta(hours=k)
        w = lookup.get(t.strftime("%Y-%m-%dT%H"))
        if w is None:
            missing += 1
            w = synthetic_weather(t)
        out.append((t, {**w, "rain": w["rain"] or 0.0}))
    return out, missing == 0


def leaf_wet_forecast(weather, wet_rh, rain_mm):
    return [w["rh"] >= wet_rh or w["rain"] >= rain_mm for _, w in weather]


def wet_from_watering(weather, at, forecast_wet, cfg):
    """Hours of leaf wetness caused by watering at index `at` that the forecast alone would not have."""
    if at is None or not cfg["irrigation_wets_leaves"]:
        return 0
    lo, hi = cfg["drying_hours"]
    added = 0
    for k in range(at, min(len(weather), at + cfg["max_wet_hours_after_watering"])):
        t, _ = weather[k]
        if k > at and lo <= t.hour < hi and not forecast_wet[k]:
            break
        if not forecast_wet[k]:
            added += 1
    return added


def simulate(start_moisture, weather, at, water_mm, sim_cfg, wet_rh, rain_mm, band):
    """Run the bucket model hourly; returns moisture per hour and time outside the band."""
    state = {"soil_moisture_pct": start_moisture, "soil_ec_ds_m": 1.0, "soil_temp_c": 27.0, "battery_pct": 100.0}
    rng = random.Random(0)
    series = []
    for k, (t, w) in enumerate(weather):
        state, _ = step(state, w, t, 1.0, sim_cfg, wet_rh, rain_mm, rng, water_mm=water_mm if k == at else 0.0)
        series.append(state["soil_moisture_pct"])
    lo, hi = band
    dry = sum(1 for m in series if lo is not None and m < lo)
    wet = sum(1 for m in series if hi is not None and m > hi)
    out = sum((lo - m if lo is not None and m < lo else 0) + (m - hi if hi is not None and m > hi else 0) for m in series)
    series = series or [start_moisture]
    return {"final_pct": series[-1], "hours_dry": dry, "hours_wet": wet, "mean_out_pct": round(out / len(series), 2),
            "min_pct": round(min(series), 1), "max_pct": round(max(series), 1)}


def moisture_before(ctx, at):
    """Projected soil moisture just before watering at index `at` (no irrigation until then)."""
    if at == 0:
        return ctx["moisture"]
    return simulate(ctx["moisture"], ctx["weather"][:at], None, 0, ctx["sim_cfg"], ctx["wet_rh"], ctx["rain_mm"],
                    ctx["band"])["final_pct"]


def slot_indexes(weather, times):
    """Index of every forecast hour whose local HH:MM matches a candidate time."""
    wanted = {int(t.split(":")[0]) for t in times}
    return [k for k, (t, _) in enumerate(weather) if t.hour in wanted]


def _candidate(ctx, at, litres, kind="option"):
    weather, area = ctx["weather"], ctx["area"]
    mm = litres / area
    sim = simulate(ctx["moisture"], weather, at, mm, ctx["sim_cfg"], ctx["wet_rh"], ctx["rain_mm"], ctx["band"])
    added = wet_from_watering(weather, at, ctx["forecast_wet"], ctx["cfg"]["water"]) if litres else 0
    w = ctx["cfg"]["weights"]
    score = w["moisture"] * sim["mean_out_pct"] + w["leaf_wet"] * added + w["water"] * mm
    blocked = []
    if at is not None:
        t = weather[at][0]
        lim, wl = ctx["limits"]["water"], ctx["water_rules"]
        if litres > lim["max_command"]:
            blocked.append("amount_over_command")
        used = ctx["used_today"] if t.date() == ctx["today"] else 0
        if used + litres > lim["max_day"]:
            blocked.append("water_daily_limit")
        rain = sum(x["rain"] for _, x in ctx["weather_long"][at:at + wl["rain_window_hours"]])
        if rain >= wl["rain_skip_mm"]:
            blocked.append("rain_forecast")
        skip = lim["skip_moisture_pct"]
        if skip is not None and moisture_before(ctx, at) >= skip:
            blocked.append("moisture_high")
    return {
        "kind": kind,
        "at": at,
        "time_local": weather[at][0].strftime("%H:%M") if at is not None else None,
        "date_local": weather[at][0].date().isoformat() if at is not None else None,
        "in_hours": at,
        "litres": round(litres, 1),
        "l_per_m2": round(mm, 2),
        "added_leaf_wet_hours": added,
        "score": round(score, 3),
        "blocked": blocked,
        **sim,
    }


def _reasons(best, skip, options):
    out = []
    if best["litres"] == 0:
        out.append({"code": "skip_best", "min_pct": skip["min_pct"]})
        if any("rain_forecast" in o["blocked"] for o in options):
            out.append({"code": "rain_expected"})
        return out
    if skip["mean_out_pct"] > best["mean_out_pct"]:
        out.append({"code": "closer_to_target", "before": round(skip["final_pct"], 1),
                    "after": round(best["final_pct"], 1)})
    if skip["hours_dry"] > best["hours_dry"]:
        out.append({"code": "fewer_dry_hours", "before": skip["hours_dry"], "after": best["hours_dry"]})
    out.append({"code": "leaf_wet", "hours": best["added_leaf_wet_hours"]})
    same = [o for o in options if o["litres"] == best["litres"] and o["at"] != best["at"] and not o["blocked"]]
    worst = max(same, key=lambda o: o["added_leaf_wet_hours"], default=None)
    if worst and worst["added_leaf_wet_hours"] > best["added_leaf_wet_hours"]:
        out.append({"code": "vs_time", "time": worst["time_local"], "hours": worst["added_leaf_wet_hours"]})
    if best["hours_wet"]:
        out.append({"code": "some_waterlogging", "hours": best["hours_wet"]})
    return out


def _fertilise(plot, weather_long, now, lim, has_doser, cfg, rain_mm_warn, rain_window):
    if not has_doser:
        return {"status": "no_doser"}
    ec = latest_value(plot, "soil_ec_ds_m", timedelta(minutes=control_config()["water"]["moisture_max_age_minutes"]), now)
    if ec is not None and lim["block_ec"] is not None and ec >= lim["block_ec"]:
        return {"status": "ec_high", "ec": ec, "limit": lim["block_ec"]}
    last = last_done(plot, "fertilise")
    earliest = (last.created_at + MYT + timedelta(hours=lim["min_hours_between"])) if last else None
    reasons = []
    for k in slot_indexes(weather_long, cfg["fertilise"]["times"]):
        t = weather_long[k][0]
        if earliest and t < earliest:
            continue
        rain = sum(x["rain"] for _, x in weather_long[k:k + rain_window])
        if rain >= rain_mm_warn:
            reasons.append({"code": "fert_rain_skip", "time": t.strftime("%Y-%m-%d %H:%M"), "mm": round(rain, 1)})
            continue
        return {"status": "ok", "time_local": t.strftime("%H:%M"), "date_local": t.date().isoformat(), "in_hours": k,
                "ec": ec, "last_amount": last.amount if last else None, "unit": lim["unit"],
                "reasons": reasons + ([{"code": "fert_spacing", "hours": lim["min_hours_between"]}] if last else [])}
    return {"status": "none_in_horizon", "hours": len(weather_long), "reasons": reasons,
            "earliest": earliest.strftime("%Y-%m-%d %H:%M") if earliest else None}


def optimise(plot, now=None):
    now = now or utcnow()
    cfg = optimizer_config()
    ccfg = control_config()
    wcfg = thresholds()["weather"]
    lim = limits(plot, ccfg)
    acts = actuators(plot)
    start = local_now(now).replace(minute=0, second=0, microsecond=0)
    weather_long, forecast_ok = hourly_weather(plot, start, max(cfg["horizon_hours"], cfg["fertilise"]["horizon_hours"]))
    weather = weather_long[:cfg["horizon_hours"]]
    band = tuple((iot_config()["targets"].get(plot.crop, {}).get("soil_moisture_pct")) or (None, None))
    moisture_reading = (SensorReading.query.filter(SensorReading.plot_id == plot.id,
                                                   SensorReading.soil_moisture_pct.isnot(None))
                        .order_by(SensorReading.ts.desc()).first())
    moisture = latest_value(plot, "soil_moisture_pct", timedelta(minutes=ccfg["water"]["moisture_max_age_minutes"]), now)
    base = {
        "plot_id": plot.id,
        "generated_at": now.isoformat() + "Z",
        "horizon_hours": cfg["horizon_hours"],
        "forecast": forecast_ok,
        "target_pct": list(band),
        "moisture_pct": moisture,
        "simulated_input": bool(moisture_reading and db.session.get(Device, moisture_reading.device_id).is_simulated),
        "limits": lim,
        "placeholder": bool(cfg.get("placeholder")),
        "label": ESTIMATE_LABEL,
        "fertilise": _fertilise(plot, weather_long, now, lim["fertilise"], any(a.kind == "doser" for a in acts), cfg,
                                ccfg["fertilise"]["rain_warn_mm"], ccfg["fertilise"]["rain_window_hours"]),
    }
    if not any(a.kind == "valve" for a in acts):
        return {**base, "status": "no_valve"}
    if moisture is None:
        return {**base, "status": "no_moisture"}

    forecast_wet = leaf_wet_forecast(weather, wcfg["leaf_wetness_rh"], wcfg["rain_mm_threshold"])
    ctx = {"weather": weather, "weather_long": weather_long, "area": lim["area_m2"], "moisture": moisture, "band": band, "cfg": cfg,
           "sim_cfg": iot_config()["simulator"], "wet_rh": wcfg["leaf_wetness_rh"], "rain_mm": wcfg["rain_mm_threshold"],
           "forecast_wet": forecast_wet, "limits": lim, "water_rules": ccfg["water"], "today": start.date(),
           "used_today": used_today(plot, "water", now)}
    skip = _candidate(ctx, None, 0, kind="skip")
    amounts = sorted({min(round(x * lim["area_m2"], 1), lim["water"]["max_command"]) for x in cfg["water"]["l_per_m2"]})
    options = [_candidate(ctx, at, litres) for at in slot_indexes(weather, cfg["water"]["times"]) for litres in amounts]
    allowed = sorted([skip] + [o for o in options if not o["blocked"]], key=lambda c: (c["score"], c["litres"]))
    best = allowed[0]
    schedules = []
    for s in ControlSchedule.query.filter_by(plot_id=plot.id, action="water", enabled=True).order_by(ControlSchedule.id):
        hour = int(s.time_local.split(":")[0])
        at = next((k for k, (t, _) in enumerate(weather) if t.hour == hour and str(t.weekday()) in s.days), None)
        if at is not None:
            schedules.append({**_candidate(ctx, at, s.amount, kind="schedule"), "schedule_id": s.id})
    return {
        **base,
        "status": "ok",
        "best": best,
        "reasons": _reasons(best, skip, options),
        "skip": skip,
        "schedules": schedules,
        "ranked": allowed[:5],
        "considered": len(options) + 1,
        "excluded": sum(1 for o in options if o["blocked"]),
        "leaf_wet_counts": cfg["water"]["irrigation_wets_leaves"],
    }
