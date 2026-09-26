"""Community spread risk per grid cell and disease.

risk = S_weather x (1 + sum_i w_dist(d_i) x w_age(t_i))
over confirmed or high-confidence reports of that disease within spread_radius_km.
"""
import json
import logging
import math
from datetime import timedelta

from ..extensions import cache
from ..models import Plot, Scan
from .config_loader import disease_profiles, tomcast_table, thresholds
from .grid import cell_center, cell_id, haversine_km
from .profiles import get_profile
from .sim_weather import series as sim_series
from .weather import get_forecasts_for_cells, now_local
from .weather_models import weather_score

log = logging.getLogger(__name__)

KM_PER_DEG = 111.0
SCENARIOS = ("live", "demo")
VERSION_KEY = "risk:version"


def w_dist(d_km, radius_km):
    return max(0.0, 1.0 - d_km / radius_km)


def w_age(age_days, decay_days):
    if age_days < 0:
        return 0.0
    return max(0.0, 1.0 - age_days / decay_days)


def risk_score(s_weather, weights):
    return s_weather * (1 + sum(weights))


def band(score, bands):
    """Medium is strictly above its cut-off so weather alone (max 1.0) never leaves Low."""
    if score >= bands["high"]:
        return "high"
    if score > bands["medium"]:
        return "medium"
    return "low"


def spreading_diseases():
    """(crop, disease) pairs that the risk map covers: everything except non-spreading profiles."""
    return [k for k, p in disease_profiles().items() if p["spread_mode"] != "none"]


def reports(crop, disease, simulated, now, decay_days):
    """Confirmed reports, or unreviewed real-model reports above the confidence threshold."""
    min_conf = thresholds()["risk"]["report_min_confidence"]
    rows = Scan.query.filter(
        Scan.crop == crop, Scan.is_simulated.is_(simulated), Scan.created_at >= now - timedelta(days=decay_days),
    ).all()
    out = []
    for s in rows:
        if s.review_status in ("confirmed", "corrected"):
            ok = s.confirmed_label == disease
        else:
            ok = s.review_status == "none" and not s.is_stub and s.diagnosis == disease and s.confidence >= min_conf
        if ok:
            out.append(s)
    return out


def cells_near(lat, lon, radius_km, cell_deg):
    k = math.ceil(radius_km / (cell_deg * KM_PER_DEG)) + 1
    i0, j0 = (int(x) for x in cell_id(lat, lon, cell_deg).split("_"))
    found = []
    for i in range(i0 - k, i0 + k + 1):
        for j in range(j0 - k, j0 + k + 1):
            cid = f"{i}_{j}"
            clat, clon = cell_center(cid, cell_deg)
            if haversine_km(lat, lon, clat, clon) <= radius_km:
                found.append(cid)
    return found


def active_cells(crop, simulated, report_rows, radius_km, cell_deg):
    cells = set()
    for r in report_rows:
        cells.update(cells_near(r.lat, r.lon, radius_km, cell_deg))
        cells.add(r.grid_cell)
    if not simulated:
        cells.update(p.grid_cell for p in Plot.query.filter_by(crop=crop, is_simulated=False).all())
    return sorted(cells)


def compute(crop, disease, horizon, scenario="live", now=None, forecasts=None):
    cfg = thresholds()
    if horizon not in cfg["risk"]["horizons_days"]:
        raise ValueError(f"horizon must be one of {cfg['risk']['horizons_days']}")
    if scenario not in SCENARIOS:
        raise ValueError("scenario must be live or demo")
    profile = get_profile(crop, disease)
    if profile is None or profile["spread_mode"] == "none":
        raise ValueError("no spread profile for this crop/disease")
    simulated = scenario == "demo"
    now = now or now_local()
    target = now + timedelta(days=horizon)
    radius, decay = profile["spread_radius_km"], profile["report_decay_days"]
    cell_deg = cfg["grid"]["cell_deg"]

    rows = reports(crop, disease, simulated, now, decay)
    cells = active_cells(crop, simulated, rows, radius, cell_deg)
    if forecasts is None:
        forecasts = {c: sim_series(c, now.date()) for c in cells} if simulated else get_forecasts_for_cells(cells)
    table = tomcast_table()

    out = []
    for cid in cells:
        clat, clon = cell_center(cid, cell_deg)
        s = weather_score(profile["weather_model"], forecasts.get(cid), target.date(), profile, cfg["risk"], cfg["weather"], table)
        weights = []
        for r in rows:
            w = w_dist(haversine_km(clat, clon, r.lat, r.lon), radius) * w_age((target - r.created_at).total_seconds() / 86400, decay)
            if w > 0:
                weights.append(w)
        score = risk_score(s, weights) if s is not None else None
        half = cell_deg / 2
        out.append({
            "cell": cid, "lat": round(clat, 4), "lon": round(clon, 4),
            "bounds": [[round(clat - half, 4), round(clon - half, 4)], [round(clat + half, 4), round(clon + half, 4)]],
            "s_weather": round(s, 3) if s is not None else None,
            "report_weight": round(sum(weights), 3),
            "reports": len(weights),
            "risk": round(score, 3) if score is not None else None,
            "band": band(score, cfg["risk"]["bands"]) if score is not None else "unknown",
        })
    return {
        "crop": crop, "disease": disease, "name": profile["name"], "weather_model": profile["weather_model"],
        "horizon": horizon, "date": target.date().isoformat(), "scenario": scenario, "simulated": simulated,
        "label": "Simulated scenario" if simulated else None,
        "bands": cfg["risk"]["bands"],
        "counts": {b: sum(1 for c in out if c["band"] == b) for b in ("low", "medium", "high", "unknown")},
        "cells": out,
        "report_points": [
            {"lat": r.lat, "lon": r.lon, "age_days": round((now - r.created_at).total_seconds() / 86400, 1)} for r in rows
        ],
        "generated_at": now.isoformat(timespec="minutes"),
    }


# ---------- caching ----------

def _version():
    try:
        return cache.client.get(VERSION_KEY) or "0"
    except Exception:  # noqa: BLE001 – cache is optional for correctness
        return "0"


def invalidate():
    """Bump the risk cache version; call after new scans or when demo data changes."""
    try:
        cache.client.incr(VERSION_KEY)
    except Exception:  # noqa: BLE001
        log.warning("could not invalidate risk cache", exc_info=True)


def _key(scenario, crop, disease, horizon):
    return f"risk:{_version()}:{scenario}:{crop}:{disease}:{horizon}"


def get_risk(crop, disease, horizon, scenario="live", refresh=False):
    key = _key(scenario, crop, disease, horizon)
    if not refresh:
        try:
            cached = cache.client.get(key)
        except Exception:  # noqa: BLE001
            cached = None
        if cached:
            return json.loads(cached)
    result = compute(crop, disease, horizon, scenario)
    try:
        cache.client.set(key, json.dumps(result), ex=thresholds()["risk"]["cache_ttl_seconds"])
    except Exception:  # noqa: BLE001
        log.warning("could not cache risk result", exc_info=True)
    return result


def refresh_all():
    """Scheduled job: refresh weather for every live active cell, then recompute and cache all risk layers."""
    cfg = thresholds()
    now = now_local()
    cells = set()
    for crop, disease in spreading_diseases():
        p = get_profile(crop, disease)
        rows = reports(crop, disease, False, now, p["report_decay_days"])
        cells.update(active_cells(crop, False, rows, p["spread_radius_km"], cfg["grid"]["cell_deg"]))
    get_forecasts_for_cells(sorted(cells), refresh=True)
    invalidate()
    n = 0
    for crop, disease in spreading_diseases():
        for h in cfg["risk"]["horizons_days"]:
            for scenario in SCENARIOS:
                get_risk(crop, disease, h, scenario)
                n += 1
    log.info("risk refresh: %d weather cells, %d layers", len(cells), n)
    return {"cells": len(cells), "layers": n}
