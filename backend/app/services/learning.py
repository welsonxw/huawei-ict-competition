"""Optimiser v2 (Phase 14): learn which watering timing did better from logged routines and outcomes.

Routine days come from completed watering commands (plus days with sensor data and no watering, as "none").
Outcomes are follow-up scans: each scan is attributed to the most common watering timing on that plot in the
`outcome_days` before it, so a scan is counted once. Harvest records give kg/m² per plot, compared by the plot's
dominant timing. Data is pooled across plots of the same crop. A timing only feeds back into the optimiser score
when it has enough logged days and scans; otherwise the v1 rules are used unchanged.
"""
from collections import Counter, defaultdict
from datetime import timedelta

from ..models import DeviceCommand, HarvestRecord, Plot, Scan, SensorReading
from ..models.core import utcnow
from .config_loader import load_config
from .control import MYT

NONE = "none"


def learning_config():
    return load_config("optimizer.yaml")["learning"]


def timing_of(hour, cfg=None):
    cfg = cfg or learning_config()
    for name, (lo, hi) in cfg["timings"].items():
        if lo <= hour < hi:
            return name
    return "night"


def timing_names(cfg):
    return [*cfg["timings"], "night", NONE]


def routine_days(plot_ids, since, cfg):
    """{(plot_id, local_date): {"timing", "litres", "simulated"}} for every day with a routine or sensor data."""
    days = {}
    cmds = (DeviceCommand.query.filter(DeviceCommand.plot_id.in_(plot_ids), DeviceCommand.action == "water",
                                       DeviceCommand.status == "done", DeviceCommand.created_at >= since)
            .order_by(DeviceCommand.created_at).all())
    for c in cmds:
        local = c.created_at + MYT
        key = (c.plot_id, local.date())
        day = days.setdefault(key, {"timing": timing_of(local.hour, cfg), "litres": 0.0, "simulated": False})
        day["litres"] += c.amount
        day["simulated"] = day["simulated"] or c.is_simulated
    readings = (SensorReading.query.with_entities(SensorReading.plot_id, SensorReading.ts)
                .filter(SensorReading.plot_id.in_(plot_ids), SensorReading.ts >= since).all())
    for plot_id, ts in readings:
        days.setdefault((plot_id, (ts + MYT).date()), {"timing": NONE, "litres": 0.0, "simulated": False})
    return days


def attribute(scan_date, plot_id, days, outcome_days):
    window = [days.get((plot_id, scan_date - timedelta(days=k))) for k in range(1, outcome_days + 1)]
    counts = Counter(d["timing"] for d in window if d)
    return counts.most_common(1)[0][0] if counts else None


def _bucket():
    return {"days": 0, "scans": 0, "sick": 0, "plots": set(), "simulated": False}


def learn(plot, now=None):
    now = now or utcnow()
    cfg = learning_config()
    since = now - timedelta(days=cfg["window_days"])
    peers = Plot.query.filter_by(crop=plot.crop).all()
    ids = [p.id for p in peers]
    days = routine_days(ids, since - timedelta(days=cfg["outcome_days"]), cfg)
    buckets = defaultdict(_bucket)
    since_local = (since + MYT).date()
    for (plot_id, d), day in days.items():
        if d < since_local:
            continue
        b = buckets[day["timing"]]
        b["days"] += 1
        b["plots"].add(plot_id)
        b["simulated"] = b["simulated"] or day["simulated"]
    scans = Scan.query.filter(Scan.plot_id.in_(ids), Scan.created_at >= since, Scan.created_at <= now).all()
    for s in scans:
        t = attribute((s.created_at + MYT).date(), s.plot_id, days, cfg["outcome_days"])
        if t is None:
            continue
        b = buckets[t]
        b["scans"] += 1
        b["sick"] += s.effective_label != "healthy"
        b["simulated"] = b["simulated"] or s.is_simulated
    total_scans = sum(b["scans"] for b in buckets.values())
    pooled = sum(b["sick"] for b in buckets.values()) / total_scans if total_scans else None
    rows = []
    for name in timing_names(cfg):
        b = buckets.get(name)
        if b is None:
            continue
        rate = b["sick"] / b["scans"] if b["scans"] else None
        enough = b["days"] >= cfg["min_days"] and b["scans"] >= cfg["min_scans"]
        rows.append({"timing": name, "days": b["days"], "scans": b["scans"], "sick": b["sick"],
                     "sick_rate": round(rate, 3) if rate is not None else None, "plots": len(b["plots"]),
                     "enough": enough, "simulated": b["simulated"]})
    qualified = [r for r in rows if r["enough"]]
    adjustments = {}
    if len(qualified) >= 2:
        adjustments = {r["timing"]: round(cfg["weight"] * (r["sick_rate"] - pooled), 3) for r in qualified}
    mine = sum(1 for (pid, d) in days if pid == plot.id and d >= since_local)
    return {
        "status": "learned" if adjustments else "learning",
        "crop": plot.crop,
        "window_days": cfg["window_days"],
        "outcome_days": cfg["outcome_days"],
        "min_days": cfg["min_days"],
        "min_scans": cfg["min_scans"],
        "pooled_sick_rate": round(pooled, 3) if pooled is not None else None,
        "timings": rows,
        "adjustments": adjustments,
        "plots": len({pid for (pid, _) in days}),
        "days_logged_here": mine,
        "simulated": any(r["simulated"] for r in rows),
        "harvest": harvest_comparison(peers, days, now, cfg),
    }


def harvest_comparison(peers, days, now, cfg):
    hcfg = cfg["harvest"]
    since = (now + MYT).date() - timedelta(days=hcfg["season_days"])
    by_timing = defaultdict(list)
    simulated = False
    for p in peers:
        records = HarvestRecord.query.filter(HarvestRecord.plot_id == p.id, HarvestRecord.harvested_on >= since).all()
        if not records or not p.area_m2:
            continue
        counts = Counter(d["timing"] for (pid, day), d in days.items() if pid == p.id and day >= since)
        if not counts:
            continue
        simulated = simulated or any(r.is_simulated for r in records)
        by_timing[counts.most_common(1)[0][0]].append(sum(r.kg for r in records) / p.area_m2)
    rows = [{"timing": t, "plots": len(v), "kg_per_m2": round(sum(v) / len(v), 2), "enough": len(v) >= hcfg["min_plots"]}
            for t, v in sorted(by_timing.items())]
    return {"season_days": hcfg["season_days"], "min_plots": hcfg["min_plots"], "timings": rows,
            "simulated": simulated}
