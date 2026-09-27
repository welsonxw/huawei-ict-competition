import random
from datetime import timedelta

import pytest
from app.models import Device, SensorReading
from app.models.core import utcnow
from app.services.config_loader import iot
from app.services.device_sim import simulate_device, step
from app.services.iot import create_device, monitor
from app.services.scans import create_plot
from conftest import login


@pytest.fixture
def plot(app):
    return create_plot("Plot A", "chilli", 1.8548, 103.3345, area_m2=400, num_plants=200)


@pytest.fixture
def no_weather(monkeypatch):
    monkeypatch.setattr("app.services.device_sim.get_forecast", lambda lat, lon: None)


def headers(device, key):
    return {"X-Device-Id": device.uid, "X-Device-Key": key}


def iso(dt):
    return dt.isoformat() + "Z"


def test_ingest_requires_valid_device_key(client, plot):
    device, key = create_device(plot)
    reading = {"soil_moisture_pct": 30}
    assert client.post("/api/iot/readings", json=reading).status_code == 401
    assert client.post("/api/iot/readings", json=reading, headers=headers(device, "wrong")).status_code == 401
    res = client.post("/api/iot/readings", json=reading, headers=headers(device, key))
    assert res.status_code == 201 and res.get_json()["accepted"] == 1
    assert res.get_json()["is_simulated"] is False
    assert device.key_hash != key and key not in str(device.to_dict())


def test_ingest_validates_values_and_batches(client, plot):
    device, key = create_device(plot)
    h = headers(device, key)
    now = utcnow()
    bad = [
        {"soil_moisture_pct": 150},
        {"air_temp_c": "hot"},
        {"leaf_wet": "yes"},
        {"ts": iso(now + timedelta(hours=1)), "air_temp_c": 30},
        {"ts": iso(now - timedelta(days=30)), "air_temp_c": 30},
        {"ts": "2026-01-01T08:00:00", "air_temp_c": 30},
        {"unknown": 1},
    ]
    for body in bad:
        assert client.post("/api/iot/readings", json=body, headers=h).status_code == 400, body
    batch = {"readings": [{"ts": iso(now - timedelta(minutes=15 * i)), "soil_moisture_pct": 30 + i,
                           "leaf_wet": True} for i in range(4)]}
    assert client.post("/api/iot/readings", json=batch, headers=h).get_json()["accepted"] == 4
    # all-or-nothing: one bad reading rejects the batch
    mixed = {"readings": [{"soil_moisture_pct": 30}, {"soil_moisture_pct": -1}]}
    assert client.post("/api/iot/readings", json=mixed, headers=h).status_code == 400
    assert SensorReading.query.count() == 4
    assert device.last_seen_at is not None


def test_monitor_requires_login(client, plot):
    assert client.get(f"/api/plots/{plot.id}/monitor").status_code == 401
    assert client.post(f"/api/plots/{plot.id}/devices", json={"simulated": True}).status_code == 401


def test_monitor_status_and_alerts(client, plot):
    login(client, "farmer")
    device, key = create_device(plot)
    now = utcnow()
    readings = [{"ts": iso(now - timedelta(minutes=30 * i)), "soil_moisture_pct": 15.0, "air_temp_c": 30,
                 "air_rh_pct": 95, "leaf_wet": True, "battery_pct": 10} for i in range(16)]
    client.post("/api/iot/readings", json={"readings": readings}, headers=headers(device, key))
    body = client.get(f"/api/plots/{plot.id}/monitor?hours=24").get_json()
    assert body["latest"]["soil_moisture_pct"]["value"] == 15.0
    assert body["status"]["soil_moisture_pct"] == "low" and body["status"]["air_temp_c"] == "ok"
    codes = {a["code"] for a in body["alerts"]}
    assert {"soil_moisture_pct_low", "air_rh_pct_high", "leaf_wet_long", "battery_low"} <= codes
    assert "offline" not in codes
    assert body["leaf_wet_hours"] == 7.5
    assert body["simulated"] is False and body["label"] is None
    assert body["targets_placeholder"] is True
    assert len(body["history"]) == 16


def test_monitor_flags_offline_device(app, plot):
    device, _ = create_device(plot)
    device.last_seen_at = utcnow() - timedelta(minutes=iot()["offline_minutes"] + 5)
    body = monitor(plot)
    assert body["devices"][0]["online"] is False
    assert any(a["code"] == "offline" for a in body["alerts"])


def test_add_simulated_device_backfills_and_is_labelled(client, plot, no_weather):
    login(client, "farmer")
    res = client.post(f"/api/plots/{plot.id}/devices", json={"simulated": True})
    body = res.get_json()
    assert res.status_code == 201 and body["key"] is None and body["is_simulated"] is True
    hours = iot()["simulator"]["initial_backfill_hours"]
    assert body["readings_added"] == hours * 60 // iot()["simulator"]["interval_minutes"] + 1
    mon = client.get(f"/api/plots/{plot.id}/monitor").get_json()
    assert mon["simulated"] is True and mon["label"] == "Simulated device"
    assert all(r["is_simulated"] for r in mon["history"])
    assert mon["devices"][0]["online"] is True


def test_real_device_key_returned_once(client, plot):
    login(client, "farmer")
    body = client.post(f"/api/plots/{plot.id}/devices", json={"name": "ESP32 north bed"}).get_json()
    assert body["key"] and body["is_simulated"] is False and body["name"] == "ESP32 north bed"
    listed = client.get(f"/api/plots/{plot.id}/devices").get_json()
    assert "key" not in listed[0] and "key_hash" not in listed[0]


def test_simulator_is_idempotent_and_resumes(app, plot, no_weather):
    device, _ = create_device(plot, simulated=True)
    now = utcnow()
    first = simulate_device(device, now=now)
    assert first > 0
    assert simulate_device(device, now=now) == 0
    assert simulate_device(device, now=now + timedelta(hours=1)) == 4
    ts = [r.ts for r in SensorReading.query.order_by(SensorReading.ts)]
    assert len(ts) == len(set(ts))


def test_step_physics(app):
    cfg = iot()["simulator"]
    state = {"soil_moisture_pct": 30.0, "soil_ec_ds_m": 1.5, "soil_temp_c": 27.0, "battery_pct": 90.0}
    noon = utcnow().replace(hour=13, minute=0)
    rng = random.Random(0)
    dry, _ = step(state, {"temp": 32, "rh": 55, "rain": 0.0}, noon, 1.0, cfg, 90, 0.5, rng)
    wet, reading = step(state, {"temp": 25, "rh": 96, "rain": 8.0}, noon, 1.0, cfg, 90, 0.5, rng)
    assert dry["soil_moisture_pct"] < 30.0 < wet["soil_moisture_pct"] <= cfg["saturation_pct"]
    assert reading["leaf_wet"] is True
    night, reading = step(state, {"temp": 24, "rh": 80, "rain": 0.0}, noon.replace(hour=2), 1.0, cfg, 90, 0.5, rng)
    assert night["soil_moisture_pct"] == pytest.approx(30.0) and reading["light_lux"] == 0
    assert reading["leaf_wet"] is False
    irrigated, _ = step(state, {"temp": 30, "rh": 70, "rain": 0.0}, noon, 1.0, cfg, 90, 0.5, rng, water_mm=10)
    assert irrigated["soil_moisture_pct"] > 30.0


def test_simulated_devices_only_advanced_by_simulator(app, plot, no_weather):
    from app.services.device_sim import run_simulated_devices

    real, _ = create_device(plot)
    sim, _ = create_device(plot, simulated=True)
    out = run_simulated_devices()
    assert set(out) == {sim.uid}
    assert SensorReading.query.filter_by(device_id=real.id).count() == 0
    assert Device.query.count() == 2


def test_external_simulated_device_uses_http_not_scheduler(client, plot, no_weather):
    from app.services.device_sim import run_simulated_devices

    device, key = create_device(plot, simulated=True, external=True)
    assert run_simulated_devices() == {}
    res = client.post("/api/iot/readings", json={"soil_moisture_pct": 30}, headers=headers(device, key))
    assert res.get_json()["is_simulated"] is True
    assert SensorReading.query.one().is_simulated is True
