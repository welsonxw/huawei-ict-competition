"""Nation layer: tonnes of harvest at risk and supply risk level per state.

tonnes_at_risk = P_region x incidence x f(severity), summed over diseases, where P_region is the expected
harvest in the window (DOA annual production x window_days / 365).
"""
import json
import logging
from datetime import timedelta

from ..extensions import cache
from ..models import Scan
from .config_loader import damage_functions, production, regions, thresholds
from .risk_engine import cache_version
from .weather import now_local

log = logging.getLogger(__name__)
CROPS = ("chilli", "tomato")
NOTE = {
    "en": "Scan data comes from app users, not a random survey, so early incidence may be over-estimated.",
    "ms": "Data imbasan datang daripada pengguna aplikasi, bukan tinjauan rawak, jadi insiden awal mungkin terlebih anggar.",
}


def damage(crop, disease, severity):
    cfg = damage_functions()
    fn = cfg["diseases"].get(f"{crop}:{disease}") or cfg["default"]
    if fn["type"] != "linear":
        raise ValueError(f"unsupported damage function {fn['type']}")
    return min(1.0, max(0.0, fn["slope"] * severity)), bool(fn.get("placeholder"))


def level(share, bands):
    if share >= bands["high"]:
        return "high"
    if share >= bands["watch"]:
        return "watch"
    return "low"


def usable(scan):
    """Pending or stub scans have no trustworthy label yet."""
    if scan.review_status in ("confirmed", "corrected"):
        return True
    return scan.review_status == "none" and not scan.is_stub


def summarise_region(scans, crop, p_window, cfg):
    n = len(scans)
    diseased = {}
    for s in scans:
        label = s.effective_label
        if label != "healthy":
            diseased.setdefault(label, []).append(s.severity or 0.0)
    by_disease, share, placeholder = [], 0.0, False
    for disease, sev in sorted(diseased.items()):
        incidence = len(sev) / n
        mean_sev = sum(sev) / len(sev)
        f, ph = damage(crop, disease, mean_sev)
        placeholder |= ph
        share += incidence * f
        by_disease.append({"disease": disease, "scans": len(sev), "incidence": round(incidence, 4),
                           "severity": round(mean_sev, 3), "damage": round(f, 3)})
    enough = n >= cfg["min_scans"]
    return {
        "scans": n,
        "diseased": sum(len(v) for v in diseased.values()),
        "share_at_risk": round(share, 4) if enough else None,
        "tonnes_at_risk": round(p_window * share, 1) if enough else None,
        "level": level(share, cfg["supply_bands"]) if enough else "insufficient",
        "by_disease": by_disease,
        "damage_placeholder": placeholder,
    }


def _scans(simulated, since, until):
    rows = Scan.query.filter(Scan.is_simulated.is_(simulated), Scan.created_at >= since, Scan.created_at <= until).all()
    return [s for s in rows if usable(s)]


def compute(scenario="live", now=None):
    if scenario not in ("live", "demo"):
        raise ValueError("scenario must be live or demo")
    cfg = thresholds()["national"]
    prod = production()
    simulated = scenario == "demo"
    now = now or now_local()
    window = timedelta(days=cfg["window_days"])
    trend_start = now - timedelta(days=cfg["trend_days"] - 1)
    all_scans = _scans(simulated, trend_start - window, now)

    def window_scans(end):
        return [s for s in all_scans if end - window < s.created_at <= end]

    current = window_scans(now)
    out = {"crops": {}}
    for crop in CROPS:
        rows = []
        for r in regions():
            annual = prod["tonnes"][crop].get(r["code"], 0)
            p_window = annual * cfg["window_days"] / 365
            scans = [s for s in current if s.crop == crop and s.region == r["code"]]
            rows.append({"code": r["code"], "name": r["name"], "production_t_year": annual,
                         "production_t_window": round(p_window, 1), **summarise_region(scans, crop, p_window, cfg)})
        rows.sort(key=lambda x: (x["tonnes_at_risk"] is None, -(x["tonnes_at_risk"] or 0), -(x["share_at_risk"] or 0)))
        out["crops"][crop] = {
            "regions": rows,
            "tonnes_at_risk": round(sum(x["tonnes_at_risk"] or 0 for x in rows), 1),
            "production_t_window": round(prod["national_total"][crop] * cfg["window_days"] / 365, 1),
        }

    trend = []
    for d in range(cfg["trend_days"]):
        end = trend_start + timedelta(days=d)
        scans = window_scans(end)
        point = {"date": end.date().isoformat()}
        for crop in CROPS:
            total = 0.0
            for r in regions():
                p_window = prod["tonnes"][crop].get(r["code"], 0) * cfg["window_days"] / 365
                region_scans = [s for s in scans if s.crop == crop and s.region == r["code"]]
                t = summarise_region(region_scans, crop, p_window, cfg)["tonnes_at_risk"]
                total += t or 0
            point[crop] = round(total, 1)
        trend.append(point)

    out.update({
        "scenario": scenario, "simulated": simulated, "label": "Simulated scenario" if simulated else None,
        "window_days": cfg["window_days"], "bands": cfg["supply_bands"], "min_scans": cfg["min_scans"],
        "production_source": prod["source"], "production_year": prod["year"],
        "damage_placeholder": damage_functions()["default"].get("placeholder", False),
        "note": NOTE, "trend": trend, "generated_at": now.isoformat(timespec="minutes"),
    })
    return out


def get_national(scenario="live"):
    key = f"national:{cache_version()}:{scenario}"
    try:
        cached = cache.client.get(key)
    except Exception:  # noqa: BLE001 – cache is optional for correctness
        cached = None
    if cached:
        return json.loads(cached)
    result = compute(scenario)
    try:
        cache.client.set(key, json.dumps(result), ex=thresholds()["risk"]["cache_ttl_seconds"])
    except Exception:  # noqa: BLE001
        log.warning("could not cache national result", exc_info=True)
    return result
