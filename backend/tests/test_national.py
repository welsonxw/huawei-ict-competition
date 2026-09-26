from types import SimpleNamespace

import pytest

from app.services.config_loader import state_boundaries
from app.services.grid import region_at
from app.services.national import damage, level, summarise_region, usable

CFG = {"min_scans": 4, "supply_bands": {"watch": 0.02, "high": 0.05}}


def scan(label="healthy", severity=0.0, review="none", stub=False, confirmed=None):
    return SimpleNamespace(effective_label=confirmed or label, severity=severity, review_status=review,
                           is_stub=stub, confirmed_label=confirmed)


def test_levels():
    b = CFG["supply_bands"]
    assert level(0.0, b) == "low" and level(0.02, b) == "watch" and level(0.05, b) == "high"


def test_default_damage_is_linear_placeholder(app):
    assert damage("chilli", "anthracnose", 0.4) == (0.4, True)
    assert damage("chilli", "anthracnose", 1.7)[0] == 1.0


def test_tonnes_at_risk_formula(app):
    scans = [scan("anthracnose", 0.4), scan("anthracnose", 0.2), scan(), scan(), scan("cercospora", 0.5)]
    out = summarise_region(scans, "chilli", p_window=100.0, cfg=CFG)
    # incidence 2/5 x mean severity 0.3 + 1/5 x 0.5
    assert out["share_at_risk"] == pytest.approx(0.4 * 0.3 + 0.2 * 0.5)
    assert out["tonnes_at_risk"] == pytest.approx(100 * 0.22, abs=0.1)
    assert out["level"] == "high" and out["damage_placeholder"] is True


def test_insufficient_data(app):
    out = summarise_region([scan("anthracnose", 0.5)], "chilli", 100.0, CFG)
    assert out["level"] == "insufficient" and out["tonnes_at_risk"] is None


def test_pending_and_stub_scans_are_not_counted():
    assert usable(scan()) and usable(scan(review="confirmed", confirmed="healthy"))
    assert not usable(scan(review="pending")) and not usable(scan(stub=True))


@pytest.mark.parametrize("lat,lon,code", [
    (4.47, 101.38, "PHG"),   # Cameron Highlands
    (1.49, 103.74, "JHR"),   # Johor Bahru
    (3.14, 101.69, "KUL"),
    (6.12, 102.24, "KTN"),
    (5.41, 100.33, "PNG"),
])
def test_region_polygons(app, lat, lon, code):
    assert region_at(lat, lon, state_boundaries()) == code


def test_national_demo_and_live(app, client):
    from app.services.demo import clear_demo, seed_demo
    from app.services.profiles import seed_profiles

    seed_profiles()
    seed_demo()
    body = client.get("/api/national?scenario=demo").get_json()
    assert body["simulated"] is True and body["label"] == "Simulated scenario"
    johor = next(r for r in body["crops"]["chilli"]["regions"] if r["code"] == "JHR")
    assert johor["level"] == "high" and johor["production_t_year"] == 8918.99
    assert len(body["trend"]) == 14 and "over-estimated" in body["note"]["en"]
    live = client.get("/api/national?scenario=live").get_json()
    assert live["label"] is None and all(r["scans"] == 0 for r in live["crops"]["chilli"]["regions"])
    assert client.get("/api/national?scenario=bogus").status_code == 400
    clear_demo()


def test_geojson_route(client):
    body = client.get("/api/regions/geojson").get_json()
    assert {f["properties"]["code"] for f in body["features"]} >= {"JHR", "PHG", "KTN"}
