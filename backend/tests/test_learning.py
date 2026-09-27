from datetime import date, timedelta

import pytest
from app.extensions import db
from app.models import DeviceCommand, HarvestRecord, Scan, User
from app.models.core import utcnow
from app.services.iot import create_device, ingest
from app.services.learning import learn, timing_of
from app.services.optimizer import optimise
from app.services.scans import create_plot
from conftest import login
from test_optimizer import series


@pytest.fixture(autouse=True)
def weather(monkeypatch):
    monkeypatch.setattr("app.services.optimizer.get_forecast", lambda lat, lon: series())
    monkeypatch.setattr("app.services.control.get_forecast", lambda lat, lon: series())


@pytest.fixture
def plot(app):
    return create_plot("Plot A", "chilli", 1.8548, 103.3345, area_m2=100, num_plants=50)


def history(plot, days, hour_local, sick_every, simulated=True):
    """Water once a day at hour_local (MYT) for `days` days; scan daily, every `sick_every`-th scan sick."""
    valve = create_device(plot, simulated=True, kind="valve")[0]
    today = (utcnow() + timedelta(hours=8)).replace(hour=0, minute=0, second=0, microsecond=0)
    for k in range(days, 0, -1):
        day = today - timedelta(days=k)
        db.session.add(DeviceCommand(request_id=f"h{plot.id}-{k}", plot_id=plot.id, device_id=valve.id, action="water",
                                     amount=200, unit="L", source="manual", status="done", is_simulated=simulated,
                                     created_at=day + timedelta(hours=hour_local - 8)))
        db.session.add(Scan(plot_id=plot.id, crop=plot.crop, diagnosis="anthracnose" if k % sick_every == 0 else "healthy",
                            confidence=0.9, top3=[], lat=plot.lat, lon=plot.lon, grid_cell=plot.grid_cell,
                            region=plot.region, is_simulated=simulated, created_at=day + timedelta(hours=12 - 8)))
    db.session.commit()
    return valve


def test_timing_buckets(app):
    assert [timing_of(h) for h in (6, 12, 19, 2)] == ["morning", "midday", "evening", "night"]


def test_insufficient_data_stays_on_rules(plot):
    history(plot, 5, 7, 2)
    r = learn(plot)
    assert r["status"] == "learning" and r["adjustments"] == {}
    morning = next(t for t in r["timings"] if t["timing"] == "morning")
    assert morning["days"] == 5 and morning["enough"] is False and r["simulated"] is True
    assert optimise(plot)["learning"]["status"] == "learning"


def test_learns_from_pooled_plots(app, plot):
    history(plot, 30, 7, 10)                     # morning: 10% sick
    other = create_plot("Plot B", "chilli", 1.858, 103.339, area_m2=100)
    history(other, 30, 19, 2)                    # evening: 50% sick
    tomato = create_plot("Plot T", "tomato", 1.85, 103.33, area_m2=100)
    history(tomato, 30, 12, 1)                   # other crop is not pooled
    r = learn(plot)
    assert r["status"] == "learned" and r["plots"] == 2
    rates = {t["timing"]: t["sick_rate"] for t in r["timings"]}
    assert rates["morning"] < rates["evening"]
    assert r["adjustments"]["morning"] < 0 < r["adjustments"]["evening"]
    ingest(create_device(plot, name="probe")[0], [{"ts": utcnow().isoformat() + "+00:00", "soil_moisture_pct": 18}])
    o = optimise(plot)
    assert o["learning"]["status"] == "learned"
    assert o["best"]["timing"] == "morning" and o["best"]["learned_adj"] < 0
    assert any(x["code"] == "learned" for x in o["reasons"])
    evening = [c for c in o["ranked"] if c["timing"] == "evening"]
    assert all(c["learned_adj"] > 0 for c in evening)


def test_scan_counted_once(plot):
    history(plot, 20, 7, 4)
    r = learn(plot)
    assert sum(t["scans"] for t in r["timings"]) <= 20


def test_harvest_comparison(plot):
    history(plot, 20, 7, 4)
    db.session.add(HarvestRecord(plot_id=plot.id, harvested_on=date.today(), kg=250, is_simulated=True))
    db.session.commit()
    h = learn(plot)["harvest"]
    assert h["timings"] == [{"timing": "morning", "plots": 1, "kg_per_m2": 2.5, "enough": False}]
    assert h["simulated"] is True


def test_harvest_api(client, plot):
    login(client, "farmer")
    url = f"/api/plots/{plot.id}/harvests"
    assert client.post(url, json={"kg": 5, "harvested_on": date.today().isoformat()}).status_code == 404
    plot.owner_id = User.query.filter_by(username="farmer").one().id
    db.session.commit()
    assert client.post(url, json={"kg": -1, "harvested_on": date.today().isoformat()}).status_code == 400
    assert client.post(url, json={"kg": 5, "harvested_on": "tomorrow"}).status_code == 400
    future = (date.today() + timedelta(days=3)).isoformat()
    assert client.post(url, json={"kg": 5, "harvested_on": future}).status_code == 400
    r = client.post(url, json={"kg": 12.5, "harvested_on": date.today().isoformat(), "notes": "first pick"})
    assert r.status_code == 201 and r.get_json()["kg"] == 12.5
    assert len(client.get(url).get_json()["harvests"]) == 1
    body = client.get(f"/api/plots/{plot.id}/learning").get_json()
    assert body["status"] == "learning" and body["can_control"] is True


def test_expert_cannot_log_harvest(client, plot):
    login(client, "expert")
    r = client.post(f"/api/plots/{plot.id}/harvests", json={"kg": 5, "harvested_on": date.today().isoformat()})
    assert r.status_code == 403
    assert client.get(f"/api/plots/{plot.id}/learning").status_code == 200
