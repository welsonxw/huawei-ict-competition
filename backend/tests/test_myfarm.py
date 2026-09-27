from datetime import timedelta

import pytest
from app.extensions import db
from app.models import Scan, User
from app.models.core import utcnow
from app.services.iot import create_device, ingest
from app.services.myfarm import farm_view
from app.services.scans import create_plot
from conftest import login


@pytest.fixture(autouse=True)
def no_forecast(monkeypatch):
    monkeypatch.setattr("app.services.control.get_forecast", lambda lat, lon: None)


@pytest.fixture
def plot(app):
    return create_plot("Kebun A", "chilli", 1.8548, 103.3345, area_m2=100, num_plants=80)


def scan(plot, label, days=0, **kw):
    s = Scan(plot_id=plot.id, crop=plot.crop, diagnosis=label, confidence=0.9, top3=[], severity=0.3,
             lat=plot.lat, lon=plot.lon, grid_cell=plot.grid_cell, region=plot.region,
             created_at=utcnow() - timedelta(days=days), **kw)
    db.session.add(s)
    db.session.commit()
    return s


def test_farm_view_reflects_sensors_scans_and_actuators(plot):
    sensor, _ = create_device(plot, name="probe")
    ingest(sensor, [{"ts": utcnow().isoformat() + "+00:00", "soil_moisture_pct": 15}])
    create_device(plot, simulated=True, kind="valve")
    scan(plot, "anthracnose")
    scan(plot, "healthy")
    scan(plot, "healthy", review_status="corrected", confirmed_label="anthracnose")
    scan(plot, "anthracnose", days=30)
    view = farm_view(plot)
    assert view["plants"] == 50 and view["plants_total"] == 80
    assert view["soil"] == "dry" and view["rain_mm_next"] is None
    assert [s["disease"] for s in view["sick"]] == ["anthracnose", "anthracnose"]
    assert [s["expert_checked"] for s in view["sick"]] == [True, False]
    assert view["scans_recent"] == 3 and view["scans_simulated"] is False
    assert "history" not in view["sensors"]
    assert view["control"]["actuators"][0]["action"] == "water" and view["control"]["simulated"]


def test_farm_view_without_data(plot):
    plot.num_plants = None
    db.session.commit()
    view = farm_view(plot)
    assert view["plants"] == 50 and view["soil"] is None and view["sick"] == []
    assert view["sensors"]["devices"] == [] and view["control"]["actuators"] == []


def test_farm_api_access(client, plot):
    login(client, "farmer")
    assert client.get(f"/api/plots/{plot.id}/farm").status_code == 404
    plot.owner_id = User.query.filter_by(username="farmer").one().id
    db.session.commit()
    body = client.get(f"/api/plots/{plot.id}/farm").get_json()
    assert body["plot"]["id"] == plot.id and body["control"]["can_control"] is True
    client.post("/api/auth/logout")
    login(client, "expert")
    assert client.get(f"/api/plots/{plot.id}/farm").get_json()["control"]["can_control"] is False
    client.post("/api/auth/logout")
    assert client.get(f"/api/plots/{plot.id}/farm").status_code == 401


def test_game_commands_use_source_game(client, plot, monkeypatch):
    login(client, "farmer")
    plot.owner_id = User.query.filter_by(username="farmer").one().id
    db.session.commit()
    create_device(plot, simulated=True, kind="valve")
    cmd = client.post(f"/api/plots/{plot.id}/commands", json={"action": "water", "amount": 20, "source": "game"}).get_json()
    assert cmd["source"] == "game" and cmd["status"] == "awaiting_confirmation"
    done = client.post(f"/api/commands/{cmd['id']}/confirm").get_json()
    assert done["status"] == "done" and done["is_simulated"] is True
    log = client.get(f"/api/plots/{plot.id}/farm").get_json()["control"]["commands"]
    assert log[0]["source"] == "game"
