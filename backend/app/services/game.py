"""Farm-game outlook: the real risk engine and action plans, read for one farm location.

The game itself (growth, coins, infection dice) runs in the browser; this only supplies
per-disease risk bands for today/+3/+5 days, the 48 h weather summary and the action plan.
Nothing is written to the database.
"""
import logging

from .action_plan import action_plan
from .config_loader import thresholds
from .grid import cell_id
from .profiles import get_profile
from .risk_engine import get_risk, spreading_diseases
from .sim_weather import series as sim_series
from .weather import get_forecast, now_local, summarise

log = logging.getLogger(__name__)

FARM_NAME = {"en": "your farm", "ms": "ladang anda"}


def _band_at(layer, cid):
    for c in layer["cells"]:
        if c["cell"] == cid:
            return c["band"], c["reports"]
    # Farm cell has no nearby reports or plots, so it is outside the computed grid:
    # weather alone never exceeds Low (see docs/ASSUMPTIONS.md).
    return "low", 0


def outlook(lat, lon, scenario="live"):
    cfg = thresholds()
    cid = cell_id(lat, lon, cfg["grid"]["cell_deg"])
    now = now_local()
    if scenario == "demo":
        forecast = sim_series(cid, now.date())
    else:
        try:
            forecast = get_forecast(lat, lon)
        except Exception:
            log.warning("forecast unavailable for game outlook", exc_info=True)
            forecast = None
    wcfg = cfg["weather"]
    diseases = []
    for crop, disease in spreading_diseases():
        profile = get_profile(crop, disease)
        bands, reports = {}, 0
        for h in cfg["risk"]["horizons_days"]:
            b, n = _band_at(get_risk(crop, disease, h, scenario), cid)
            bands[str(h)] = b
            reports = max(reports, n)
        plan = action_plan(disease, crop, profile, FARM_NAME["en"], forecast, wcfg, now=now)
        plan_ms = action_plan(disease, crop, profile, FARM_NAME["ms"], forecast, wcfg, now=now)
        diseases.append({
            "crop": crop, "disease": disease, "name": profile["name"], "advice_type": profile["advice_type"],
            "bands": bands, "reports": reports, "plan": {"en": plan["en"], "ms": plan_ms["ms"]},
        })
    return {
        "lat": lat, "lon": lon, "cell": cid, "scenario": scenario,
        "simulated": scenario == "demo", "label": "Simulated scenario" if scenario == "demo" else None,
        "horizons": cfg["risk"]["horizons_days"],
        "weather": summarise(forecast, wcfg["action_plan_hours"], wcfg["rain_mm_threshold"], wcfg["leaf_wetness_rh"], now),
        "diseases": diseases,
    }
