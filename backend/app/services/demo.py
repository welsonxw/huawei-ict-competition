"""Simulated scenario seeder: chilli anthracnose spreading from one area in Johor during a rainy spell,
plus scattered tomato early blight. Every row is is_simulated = true. NOT real data."""
import math
import random
from datetime import timedelta

from ..extensions import db
from ..models import Plot, Scan
from .config_loader import demo_scenario
from .risk_engine import invalidate
from .scans import locate
from .weather import now_local

KM_PER_DEG = 111.0


def _point(rng, lat, lon, radius_km):
    r = radius_km * math.sqrt(rng.random())
    a = rng.uniform(0, 2 * math.pi)
    return lat + r * math.cos(a) / KM_PER_DEG, lon + r * math.sin(a) / (KM_PER_DEG * math.cos(math.radians(lat)))


def _scan(rng, crop, disease, lat, lon, when):
    conf = round(rng.uniform(0.82, 0.98), 3)
    cell, region = locate(lat, lon)
    return Scan(
        crop=crop, diagnosis=disease, confidence=conf,
        top3=[{"label": disease, "confidence": conf}, {"label": "healthy", "confidence": round((1 - conf) * 0.7, 3)}],
        severity=round(rng.uniform(0.05, 0.6), 3), lat=round(lat, 5), lon=round(lon, 5), grid_cell=cell, region=region,
        model_version="simulated", is_stub=False, review_status="none", is_simulated=True, created_at=when,
    )


def clear_demo():
    n = Scan.query.filter_by(is_simulated=True).delete()
    Plot.query.filter_by(is_simulated=True).delete()
    db.session.commit()
    invalidate()
    return n


def seed_demo(now=None):
    cfg = demo_scenario()
    clear_demo()
    rng = random.Random(cfg["seed"])
    now = now or now_local()
    days = cfg["days"]
    start = now - timedelta(days=days - 1)
    rows = []

    a = cfg["chilli_anthracnose"]
    for k in range(days):
        radius = a["start_radius_km"] + a["growth_km_per_day"] * k
        for _ in range(round(a["scans_first_day"] + a["scans_added_per_day"] * k)):
            when = start + timedelta(days=k, hours=rng.uniform(7, 18))
            if when > now:
                when = now - timedelta(minutes=rng.uniform(5, 120))
            lat, lon = _point(rng, a["origin"]["lat"], a["origin"]["lon"], radius)
            rows.append(_scan(rng, "chilli", "anthracnose", lat, lon, when))

    for c in cfg["tomato_early_blight"]["clusters"]:
        for _ in range(c["count"]):
            when = now - timedelta(days=rng.uniform(0, days - 1))
            lat, lon = _point(rng, c["lat"], c["lon"], c["radius_km"])
            rows.append(_scan(rng, "tomato", "early_blight", lat, lon, when))

    db.session.add_all(rows)
    db.session.commit()
    invalidate()
    return len(rows)


def demo_count():
    return Scan.query.filter_by(is_simulated=True).count()
