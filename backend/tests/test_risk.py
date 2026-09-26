from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.services import weather_models as wm
from app.services.config_loader import thresholds, tomcast_table
from app.services.risk_engine import band, compute, risk_score, w_age, w_dist

DAY = date(2026, 3, 10)
CONFIG = Path(__file__).resolve().parents[2] / "config"
RISK = thresholds(CONFIG)["risk"]
WX = thresholds(CONFIG)["weather"]
TABLE = tomcast_table(CONFIG)


def make_series(days, temp=25.0, rh=70.0, rain=0.0, per_day=None):
    """Hourly series for `days` days ending on DAY. per_day(i, hour) -> (temp, rh, rain) overrides."""
    start = datetime.combine(DAY - timedelta(days=days - 1), datetime.min.time())
    s = {"time": [], "temp": [], "rh": [], "rain": []}
    for i in range(days * 24):
        t, h, r = per_day(i // 24, i % 24) if per_day else (temp, rh, rain)
        s["time"].append((start + timedelta(hours=i)).isoformat(timespec="minutes"))
        s["temp"].append(t)
        s["rh"].append(h)
        s["rain"].append(r)
    return s


# ---- TOM-CAST ----

@pytest.mark.parametrize("wet,temp,expected", [
    (0, 22, 0), (2, 22, 0), (3, 22, 1), (6, 22, 2), (13, 22, 3), (21, 22, 4),
    (4, 19, 1), (23, 19, 4), (7, 15, 1), (21, 15, 3), (10, 12, 0), (24, 31, 0),
])
def test_dsv_table(wet, temp, expected):
    assert wm.dsv(wet, temp, TABLE) == expected


def test_tomcast_accumulates_and_normalises_to_threshold():
    # 13 wet hours at 22 °C every day -> DSV 3/day, 7 days -> 21 >= 15 -> score 1.
    wet = make_series(7, per_day=lambda d, h: (22.0, 95.0 if h < 13 else 60.0, 0.0))
    assert wm.weather_score("tomcast", wet, DAY, {}, RISK, WX, TABLE) == 1.0
    # 3 wet hours/day -> DSV 1/day -> 7/15.
    light = make_series(7, per_day=lambda d, h: (22.0, 95.0 if h < 3 else 60.0, 0.0))
    assert wm.weather_score("tomcast", light, DAY, {}, RISK, WX, TABLE) == pytest.approx(7 / 15)
    assert wm.weather_score("tomcast", make_series(7), DAY, {}, RISK, WX, TABLE) == 0.0


# ---- Hutton ----

HUTTON = {"temp_min": 10, "moisture": {"rh_min": 90, "rh_hours": 6, "consecutive_days": 2}}


def test_hutton_full_near_miss_and_none():
    both = make_series(2, per_day=lambda d, h: (15.0, 95.0 if h < 6 else 70.0, 0.0))
    one = make_series(2, per_day=lambda d, h: (15.0, 95.0 if (d == 1 and h < 6) else 70.0, 0.0))
    cold = make_series(2, per_day=lambda d, h: (8.0 if h == 3 else 15.0, 95.0, 0.0))
    assert wm.weather_score("hutton", both, DAY, HUTTON, RISK, WX, TABLE) == 1.0
    assert wm.weather_score("hutton", one, DAY, HUTTON, RISK, WX, TABLE) == 0.5
    assert wm.weather_score("hutton", cold, DAY, HUTTON, RISK, WX, TABLE) == 0.0


# ---- rule ----

ANTHRACNOSE = {"temp_min": 20, "temp_max": 30, "moisture": {"rh_min": 80, "rain_events": True}}


def test_rule_counts_favourable_hours():
    wet = make_series(3, temp=25.0, rh=85.0)
    dry = make_series(3, temp=25.0, rh=60.0)
    hot = make_series(3, temp=34.0, rh=90.0)
    half = make_series(3, per_day=lambda d, h: (25.0, 85.0 if h < 9 else 60.0, 0.0))  # 9/24 = 0.375
    assert wm.weather_score("rule", wet, DAY, ANTHRACNOSE, RISK, WX, TABLE) == 1.0
    assert wm.weather_score("rule", dry, DAY, ANTHRACNOSE, RISK, WX, TABLE) == 0.0
    assert wm.weather_score("rule", hot, DAY, ANTHRACNOSE, RISK, WX, TABLE) == 0.0
    assert wm.weather_score("rule", half, DAY, ANTHRACNOSE, RISK, WX, TABLE) == pytest.approx(0.375 / 0.75)
    rain = make_series(3, per_day=lambda d, h: (25.0, 60.0, 2.0 if h < 9 else 0.0))
    assert wm.weather_score("rule", rain, DAY, ANTHRACNOSE, RISK, WX, TABLE) == pytest.approx(0.5)


# ---- vector proxy ----

def test_vector_proxy_hot_dry_high_rain_suppresses():
    hot_dry = make_series(7, temp=33.0, rh=60.0)
    cool_wet = make_series(7, temp=24.0, rh=90.0, rain=1.0)
    rain_today = make_series(7, per_day=lambda d, h: (33.0, 60.0, 2.0 if d == 6 and h == 15 else 0.0))
    assert wm.weather_score("vector_proxy", hot_dry, DAY, {}, RISK, WX, TABLE) == 1.0
    assert wm.weather_score("vector_proxy", cool_wet, DAY, {}, RISK, WX, TABLE) == 0.0
    s = wm.weather_score("vector_proxy", rain_today, DAY, {}, RISK, WX, TABLE)
    assert s == pytest.approx((0.5 * 6 / 7 + 0.5) * 0.5)


def test_none_model_and_missing_weather():
    assert wm.weather_score("none", None, DAY, {}, RISK, WX, TABLE) == 1.0
    assert wm.weather_score("rule", None, DAY, ANTHRACNOSE, RISK, WX, TABLE) is None


# ---- risk formula ----

def test_weights_are_linear():
    assert w_dist(0, 5) == 1 and w_dist(2.5, 5) == 0.5 and w_dist(6, 5) == 0
    assert w_age(0, 14) == 1 and w_age(7, 14) == 0.5 and w_age(20, 14) == 0 and w_age(-1, 14) == 0


def test_risk_formula_and_bands():
    assert risk_score(0.5, []) == 0.5
    assert risk_score(0.5, [1.0, 0.5]) == pytest.approx(0.5 * 2.5)
    bands = {"medium": 1.0, "high": 2.0}
    assert band(1.0, bands) == "low" and band(1.01, bands) == "medium" and band(2.0, bands) == "high"


def test_compute_uses_nearby_reports(app):
    from app.extensions import db
    from app.models import Scan
    from app.services.profiles import seed_profiles
    from app.services.scans import locate

    seed_profiles()
    now = datetime(2026, 3, 10, 12, 0)
    lat, lon = 1.99, 103.32
    cell, region = locate(lat, lon)
    base = dict(crop="chilli", diagnosis="anthracnose", top3=[], lat=lat, lon=lon, grid_cell=cell, region=region)
    db.session.add_all([
        Scan(confidence=0.9, created_at=now - timedelta(days=1), **base),
        Scan(confidence=0.5, created_at=now, **base),                                 # too uncertain
        Scan(confidence=0.9, created_at=now, review_status="pending", **base),        # awaiting review
        Scan(confidence=0.5, created_at=now, review_status="confirmed", confirmed_label="anthracnose", **base),
        Scan(confidence=0.9, created_at=now, is_simulated=True, **base),              # other scenario
    ])
    db.session.commit()
    wet = make_series(3, temp=25.0, rh=85.0)
    out = compute("chilli", "anthracnose", 0, "live", now=now, forecasts=_all(wet))
    home = next(c for c in out["cells"] if c["cell"] == cell)
    assert home["reports"] == 2 and home["s_weather"] == 1.0
    assert home["risk"] == pytest.approx(1.0 * (1 + home["report_weight"]), abs=1e-3)
    assert home["band"] in ("medium", "high") and out["simulated"] is False and out["label"] is None
    assert len(out["report_points"]) == 2


class _all(dict):
    def __init__(self, series):
        super().__init__()
        self.series = series

    def get(self, key, default=None):
        return self.series


def test_demo_outbreak_grows_across_slider(app, client):
    from app.services.demo import clear_demo, seed_demo
    from app.services.profiles import seed_profiles

    from app.models import Scan

    seed_profiles()
    seed_demo()
    assert Scan.query.filter_by(is_simulated=False).count() == 0
    assert 250 <= Scan.query.filter_by(diagnosis="anthracnose", is_simulated=True).count() <= 350
    counts = []
    for h in (0, 3, 5):
        body = client.get(f"/api/risk?crop=chilli&disease=anthracnose&horizon={h}&scenario=demo").get_json()
        assert body["simulated"] is True and body["label"] == "Simulated scenario"
        counts.append(body["counts"]["medium"] + body["counts"]["high"])
    assert counts[0] < counts[1] <= counts[2]
    assert client.get("/api/risk/diseases").get_json()["demo_label"] == "Simulated scenario"
    live = client.get("/api/risk?crop=chilli&disease=anthracnose&horizon=0&scenario=live").get_json()
    assert live["cells"] == []  # simulated scans never leak into the live layer
    clear_demo()
    assert client.get("/api/risk/diseases").get_json()["demo_scans"] == 0


def test_risk_route_validation(client):
    assert client.get("/api/risk?crop=chilli&disease=nutrient_deficiency").status_code == 400
    assert client.get("/api/risk?crop=chilli&disease=anthracnose&horizon=2").status_code == 400
    assert client.get("/api/risk?crop=chilli&disease=anthracnose&horizon=x").status_code == 400
    assert client.get("/api/risk?crop=chilli&disease=anthracnose&scenario=bogus").status_code == 400


def test_batch_fetch_caches(app, monkeypatch):
    from app.extensions import cache
    from app.services import weather

    calls = []

    def fake(coords, *a, **k):
        calls.append(len(coords))
        return [make_series(1) for _ in coords]

    monkeypatch.setattr(weather, "fetch_open_meteo_many", fake)
    out = weather.get_forecasts_for_cells(["44_2296", "44_2297"])
    assert calls == [2] and all(out.values())
    assert cache.client.ttl("weather:44_2296") > 0
    weather.get_forecasts_for_cells(["44_2296", "44_2297"])
    assert calls == [2]  # served from Redis
