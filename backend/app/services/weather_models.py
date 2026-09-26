"""Weather score (0–1) per disease model, computed from an hourly series for a window ending on a target date.

Leaf wetness is approximated as hours with RH >= `leaf_wetness_rh` (see docs/ASSUMPTIONS.md).
"""
from collections import OrderedDict
from datetime import date, datetime, timedelta


def daily(series):
    """Group an hourly series into {date: [(temp, rh, rain), ...]} (skips hours with missing values)."""
    days = OrderedDict()
    for t, temp, rh, rain in zip(series["time"], series["temp"], series["rh"], series["rain"]):
        if temp is None or rh is None:
            continue
        days.setdefault(datetime.fromisoformat(t).date(), []).append((temp, rh, rain or 0.0))
    return days


def window(days, end: date, n):
    return [days[d] for d in (end - timedelta(days=i) for i in range(n - 1, -1, -1)) if d in days]


def dsv(wet_hours, mean_wet_temp, table):
    if wet_hours == 0 or mean_wet_temp is None:
        return 0
    for b in table["bins"]:
        if b["temp_min"] <= mean_wet_temp < b["temp_max"]:
            value = 0
            for min_hours, v in b["dsv"]:
                if wet_hours >= min_hours:
                    value = v
            return value
    return 0


def day_dsv(hours, wet_rh, table):
    wet = [t for t, rh, _ in hours if rh >= wet_rh]
    return dsv(len(wet), sum(wet) / len(wet) if wet else None, table)


def tomcast_score(days, end, cfg, table, wet_rh):
    win = window(days, end, cfg["tomcast"]["window_days"])
    if not win:
        return None
    return min(1.0, sum(day_dsv(h, wet_rh, table) for h in win) / table["threshold"])


def hutton_score(days, end, profile):
    """1 if both of the last 2 days meet the Hutton criteria, 0.5 if one does (near miss), else 0."""
    m = profile.get("moisture") or {}
    rh_min, rh_hours = m.get("rh_min", 90), m.get("rh_hours", 6)
    tmin = profile.get("temp_min")
    tmin = 10 if tmin is None else tmin
    n = m.get("consecutive_days", 2)
    win = window(days, end, n)
    if not win:
        return None
    ok = [min(t for t, _, _ in h) >= tmin and sum(1 for _, rh, _ in h if rh >= rh_min) >= rh_hours for h in win]
    if len(ok) == n and all(ok):
        return 1.0
    return 0.5 if any(ok) else 0.0


def rule_score(days, end, profile, cfg, rain_mm):
    """Share of hours inside the temperature range with the moisture trigger met, scaled to full_fraction."""
    win = window(days, end, cfg["rule"]["window_days"])
    hours = [h for d in win for h in d]
    if not hours:
        return None
    lo, hi = profile.get("temp_min"), profile.get("temp_max")
    m = profile.get("moisture") or {}
    rh_min, rain_events = m.get("rh_min"), m.get("rain_events", False)

    def favourable(t, rh, rain):
        in_range = (lo is None or t >= lo) and (hi is None or t <= hi)
        moist = (rh_min is not None and rh >= rh_min) or (rain_events and rain >= rain_mm)
        return in_range and moist

    frac = sum(1 for h in hours if favourable(*h)) / len(hours)
    return min(1.0, frac / cfg["rule"]["full_fraction"])


def vector_score(days, end, cfg):
    """Whitefly proxy: hot, dry spells raise the score; rain on the last day suppresses it."""
    v = cfg["vector_proxy"]
    win = window(days, end, v["window_days"])
    if not win:
        return None
    rain = [sum(r for _, _, r in h) for h in win]
    dry = sum(1 for r in rain if r < v["dry_day_mm"]) / len(win)
    mean_max = sum(max(t for t, _, _ in h) for h in win) / len(win)
    heat = min(1.0, max(0.0, (mean_max - v["temp_low"]) / (v["temp_high"] - v["temp_low"])))
    score = 0.5 * dry + 0.5 * heat
    if rain[-1] >= v["dry_day_mm"]:
        score *= v["rain_suppression"]
    return score


def weather_score(model, series, end, profile, risk_cfg, weather_cfg, table):
    if model == "none":
        return 1.0
    if not series:
        return None
    days = daily(series)
    if model == "tomcast":
        return tomcast_score(days, end, risk_cfg, table, weather_cfg["leaf_wetness_rh"])
    if model == "hutton":
        return hutton_score(days, end, profile)
    if model == "rule":
        return rule_score(days, end, profile, risk_cfg, weather_cfg["rain_mm_threshold"])
    if model == "vector_proxy":
        return vector_score(days, end, risk_cfg)
    raise ValueError(f"unknown weather model {model}")
