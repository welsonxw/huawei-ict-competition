from datetime import datetime, timedelta

import pytest
from app.extensions import db
from app.models import ControlSchedule, DeviceCommand, SensorReading, User
from app.models.core import utcnow
from app.services.control import (
    confirm_command,
    evaluate,
    expire_stale,
    limits,
    record_response,
    request_command,
    run_due_schedules,
)
from app.services.iot import create_device, ingest, monitor
from app.services.mqtt_bridge import handle_command_response
from app.services.scans import create_plot
from conftest import login


def forecast(rain_mm=0.0, hours=48, now=None):
    start = ((now or utcnow()) + timedelta(hours=8)).replace(minute=0, second=0, microsecond=0)
    times = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    return {"time": times, "rain": [rain_mm] * hours, "rh": [70] * hours, "temp": [28] * hours}


@pytest.fixture
def dry(monkeypatch):
    monkeypatch.setattr("app.services.control.get_forecast", lambda lat, lon: forecast(0.0))
    monkeypatch.setattr("app.services.device_sim.get_forecast", lambda lat, lon: None)


@pytest.fixture
def plot(app):
    return create_plot("Plot A", "chilli", 1.8548, 103.3345, area_m2=100, num_plants=50)


@pytest.fixture
def farmer(client, plot):
    login(client, "farmer")
    plot.owner_id = User.query.filter_by(username="farmer").one().id
    db.session.commit()
    return plot


def add_reading(plot, **values):
    sensor, _ = create_device(plot, name="probe")
    ingest(sensor, [{"ts": utcnow().isoformat() + "+00:00", **values}])
    return sensor


def codes(checks, level=None):
    return {c["code"] for c in checks if level is None or c["level"] == level}


def test_limits_scale_with_area(plot):
    lim = limits(plot)
    assert lim["water"]["max_command"] == 500 and lim["water"]["max_day"] == 1000
    assert lim["water"]["skip_moisture_pct"] == 40 and lim["fertilise"]["block_ec"] == 2.5
    assert lim["placeholder"] is True


def test_water_blocked_when_soil_wet_or_rain_forecast(app, plot, dry, monkeypatch):
    valve, _ = create_device(plot, simulated=True, kind="valve")
    add_reading(plot, soil_moisture_pct=45)
    assert "moisture_high" in codes(evaluate(plot, valve, "water", 50), "block")

    plot2 = create_plot("Plot B", "chilli", 1.85, 103.33, area_m2=100)
    valve2, _ = create_device(plot2, simulated=True, kind="valve")
    add_reading(plot2, soil_moisture_pct=20)
    assert not codes(evaluate(plot2, valve2, "water", 50), "block")
    monkeypatch.setattr("app.services.control.get_forecast", lambda lat, lon: forecast(2.0))
    assert "rain_forecast" in codes(evaluate(plot2, valve2, "water", 50), "block")


def test_amount_and_daily_limits(app, plot, dry):
    valve, _ = create_device(plot, simulated=True, kind="valve")
    add_reading(plot, soil_moisture_pct=20)
    assert codes(evaluate(plot, valve, "water", 0), "block") == {"amount_invalid"}
    assert "amount_over_command" in codes(evaluate(plot, valve, "water", 501), "block")
    for _ in range(2):
        cmd = request_command(plot, "water", 450)
        confirm_command(cmd)
    assert "water_daily_limit" in codes(evaluate(plot, valve, "water", 200), "block")


def test_unknown_moisture_and_forecast_are_warnings(app, plot, monkeypatch):
    monkeypatch.setattr("app.services.control.get_forecast", lambda lat, lon: None)
    valve, _ = create_device(plot, simulated=True, kind="valve")
    checks = evaluate(plot, valve, "water", 10)
    assert {"moisture_unknown", "forecast_unknown"} <= codes(checks, "warn") and not codes(checks, "block")


def test_fertilise_interval_and_ec(app, plot, dry):
    create_device(plot, simulated=True, kind="doser")
    add_reading(plot, soil_ec_ds_m=1.0)
    cmd = confirm_command(request_command(plot, "fertilise", 200))
    assert cmd.status == "done"
    again = request_command(plot, "fertilise", 100)
    assert again.status == "blocked" and "fertilise_too_soon" in codes(again.checks, "block")

    plot2 = create_plot("Plot B", "chilli", 1.85, 103.33, area_m2=100)
    create_device(plot2, simulated=True, kind="doser")
    add_reading(plot2, soil_ec_ds_m=3.1)
    assert "ec_high" in codes(request_command(plot2, "fertilise", 50).checks, "block")


def test_real_device_offline_blocks(app, plot, dry):
    valve, _ = create_device(plot, kind="valve")
    assert "device_offline" in codes(evaluate(plot, valve, "water", 10), "block")
    valve.last_seen_at = utcnow()
    db.session.commit()
    assert "device_offline" not in codes(evaluate(plot, valve, "water", 10))


def test_simulated_valve_moves_simulated_soil_moisture(app, plot, dry):
    sensor, _ = create_device(plot, simulated=True)
    from app.services.device_sim import simulate_device

    simulate_device(sensor)
    create_device(plot, simulated=True, kind="valve")
    before = monitor(plot)["latest"]["soil_moisture_pct"]["value"]
    cmd = confirm_command(request_command(plot, "water", 200))
    assert cmd.status == "done" and cmd.transport == "sim" and cmd.is_simulated
    assert cmd.result["paras"]["simulated"] is True
    after = monitor(plot)["latest"]["soil_moisture_pct"]["value"]
    assert after > before and cmd.result["paras"]["moisture_after"] > cmd.result["paras"]["moisture_before"]
    assert cmd.params == {"litres": 200.0, "duration_s": 1200}
    assert all(d["kind"] == "sensor" for d in monitor(plot)["devices"])


def test_confirm_rechecks_and_expiry(app, plot, dry):
    create_device(plot, simulated=True, kind="valve")
    add_reading(plot, soil_moisture_pct=20)
    cmd = request_command(plot, "water", 50)
    assert cmd.status == "awaiting_confirmation" and cmd.expires_at
    add_reading(plot, soil_moisture_pct=45)
    assert confirm_command(cmd).status == "blocked"

    add_reading(plot, soil_moisture_pct=20)
    late = request_command(plot, "water", 10)
    assert late.status == "awaiting_confirmation"
    late_id = late.id
    assert expire_stale(utcnow() + timedelta(minutes=10)) >= 1
    assert db.session.get(DeviceCommand, late_id).status == "expired"


def test_http_actuator_poll_and_ack(client, farmer, dry):
    valve, key = create_device(farmer, kind="valve")
    add_reading(farmer, soil_moisture_pct=20)
    h = {"X-Device-Id": valve.uid, "X-Device-Key": key}
    assert client.get("/api/iot/commands").status_code == 401
    assert client.get("/api/iot/commands", headers=h).get_json() == {"commands": []}

    res = client.post(f"/api/plots/{farmer.id}/commands", json={"action": "water", "amount": 30})
    assert res.status_code == 201 and res.get_json()["status"] == "awaiting_confirmation"
    res = client.post(f"/api/commands/{res.get_json()['id']}/confirm")
    body = res.get_json()
    assert body["status"] == "sent" and body["transport"] == "http" and body["is_simulated"] is False

    polled = client.get("/api/iot/commands", headers=h).get_json()["commands"]
    assert polled == [{"request_id": body["request_id"], "service_id": "Irrigation", "command_name": "WATER",
                       "paras": {"litres": 30.0, "duration_s": 180}}]
    other, other_key = create_device(farmer, kind="valve")
    bad = {"X-Device-Id": other.uid, "X-Device-Key": other_key}
    assert client.post(f"/api/iot/commands/{body['request_id']}/response", json={}, headers=bad).status_code == 404
    res = client.post(f"/api/iot/commands/{body['request_id']}/response",
                      json={"result_code": 0, "paras": {"result": "success"}}, headers=h)
    assert res.get_json()["status"] == "done"
    assert client.get("/api/iot/commands", headers=h).get_json() == {"commands": []}


def test_sent_command_times_out(app, plot, dry):
    valve, _ = create_device(plot, kind="valve")
    valve.last_seen_at = utcnow()
    db.session.commit()
    add_reading(plot, soil_moisture_pct=20)
    cmd = confirm_command(request_command(plot, "water", 10))
    assert cmd.status == "sent"
    assert "device_busy" in codes(evaluate(plot, valve, "water", 10), "block")
    record_response(cmd.request_id, {"result_code": 0}, device=valve, now=utcnow() + timedelta(minutes=5))
    assert cmd.status == "expired"


def test_mqtt_response_topic(app, plot, dry):
    valve, _ = create_device(plot, kind="valve")
    valve.last_seen_at = utcnow()
    db.session.commit()
    cmd = confirm_command(request_command(plot, "water", 10))
    topic = f"$oc/devices/{valve.uid}/sys/commands/response/request_id={cmd.request_id}"
    assert handle_command_response(topic, b'{"result_code": 1, "paras": {"error": "valve stuck"}}').status == "failed"
    assert handle_command_response("$oc/devices/x/sys/properties/report", b"{}") is None


def test_iotda_sync_command(app, plot, dry, monkeypatch):
    app.config.update(IOTDA_API_ENDPOINT="https://iotda.example", IOTDA_PROJECT_ID="proj", IOTDA_IAM_TOKEN="tok",
                      IOTDA_PRODUCT_ID="prod")
    valve, _ = create_device(plot, kind="valve")
    valve.last_seen_at, valve.transport = utcnow(), "iotda"
    db.session.commit()
    sent = {}

    class Res:
        status_code = 200
        content = b"x"

        def json(self):
            return {"command_id": "c-1", "response": {"result_code": 0, "paras": {"result": "success"}}}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, json=json, headers=headers)
        return Res()

    monkeypatch.setattr("app.services.control.requests.post", fake_post)
    cmd = confirm_command(request_command(plot, "water", 10))
    assert cmd.status == "done" and cmd.transport == "iotda"
    assert sent["url"] == f"https://iotda.example/v5/iot/proj/devices/prod_{valve.uid}/commands"
    assert sent["json"]["command_name"] == "WATER" and sent["headers"] == {"X-Auth-Token": "tok"}
    assert cmd.result["paras"]["iotda_command_id"] == "c-1"


def test_schedules_run_once_per_day_and_log_skips(app, plot, dry, monkeypatch):
    create_device(plot, simulated=True, kind="valve")
    add_reading(plot, soil_moisture_pct=20)
    sched = ControlSchedule(plot_id=plot.id, action="water", amount=40, time_local="07:00", days="0123456")
    db.session.add(sched)
    db.session.commit()
    now = datetime.combine((utcnow() + timedelta(hours=8)).date(), datetime.min.time()) + timedelta(hours=7, minutes=5) - timedelta(hours=8)
    early = now - timedelta(minutes=10)
    assert run_due_schedules(early) == []
    monkeypatch.setattr("app.services.control.get_forecast", lambda lat, lon: forecast(0.0, now=now))
    cmds = run_due_schedules(now)
    assert len(cmds) == 1 and cmds[0].source == "schedule" and cmds[0].status == "done"
    assert run_due_schedules(now + timedelta(minutes=5)) == []

    rainy = ControlSchedule(plot_id=plot.id, action="water", amount=40, time_local="07:00", days="0123456")
    db.session.add(rainy)
    db.session.commit()
    monkeypatch.setattr("app.services.control.get_forecast", lambda lat, lon: forecast(3.0, now=now))
    skipped = run_due_schedules(now)
    assert skipped[0].status == "blocked" and "rain_forecast" in codes(skipped[0].checks, "block")


def test_control_api_access(client, farmer, dry):
    create_device(farmer, simulated=True, kind="valve")
    res = client.get(f"/api/plots/{farmer.id}/control")
    body = res.get_json()
    assert res.status_code == 200 and body["can_control"] and body["simulated"]
    assert body["actuators"][0]["action"] == "water" and body["limits"]["water"]["max_command"] == 500

    cmd = client.post(f"/api/plots/{farmer.id}/commands", json={"action": "water", "amount": 10}).get_json()
    assert client.post(f"/api/plots/{farmer.id}/commands", json={"action": "spray", "amount": 1}).status_code == 400
    assert client.post(f"/api/plots/{farmer.id}/commands",
                       json={"action": "fertilise", "amount": 1}).get_json()["error"] == "no fertiliser doser on this plot"
    res = client.post(f"/api/plots/{farmer.id}/schedules", json={"action": "water", "amount": 20, "time_local": "25:00"})
    assert res.status_code == 400
    sched = client.post(f"/api/plots/{farmer.id}/schedules",
                        json={"action": "water", "amount": 20, "time_local": "07:30", "days": "531"}).get_json()
    assert sched["days"] == "135"
    assert client.patch(f"/api/schedules/{sched['id']}", json={"enabled": False}).get_json()["enabled"] is False

    client.post("/api/auth/logout")
    login(client, "farmer", "farmer2")
    assert client.get(f"/api/plots/{farmer.id}/control").status_code == 404
    assert client.post(f"/api/commands/{cmd['id']}/confirm").status_code == 404
    assert client.delete(f"/api/schedules/{sched['id']}").status_code == 404

    client.post("/api/auth/logout")
    login(client, "expert")
    assert client.get(f"/api/plots/{farmer.id}/control").get_json()["can_control"] is False
    assert client.post(f"/api/commands/{cmd['id']}/confirm").status_code == 403

    client.post("/api/auth/logout")
    client.post("/api/auth/login", json={"username": "farmer", "password": "password123"})
    assert client.post(f"/api/commands/{cmd['id']}/cancel").get_json()["status"] == "cancelled"
    assert client.post(f"/api/commands/{cmd['id']}/confirm").status_code == 409
    assert client.delete(f"/api/schedules/{sched['id']}").get_json() == {"deleted": sched["id"]}


def test_readings_not_duplicated_for_actuators(app, plot):
    create_device(plot, simulated=True, kind="valve")
    from app.services.device_sim import run_simulated_devices

    assert run_simulated_devices() == {}
    assert SensorReading.query.count() == 0
