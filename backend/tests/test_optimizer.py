from datetime import datetime, timedelta

import pytest
from app.extensions import db
from app.models import DeviceCommand, User
from app.models.core import utcnow
from app.services.control import create_schedule
from app.services.iot import create_device, ingest
from app.services.optimizer import optimise, wet_from_watering
from app.services.scans import create_plot
from conftest import login


def series(rh=lambda h: 70, rain=lambda h: 0.0, hours=96):
    start = (utcnow() + timedelta(hours=8)).replace(minute=0, second=0, microsecond=0)
    ts = [start + timedelta(hours=i) for i in range(hours)]
    return {"time": [t.strftime("%Y-%m-%dT%H:%M") for t in ts], "rh": [rh(t.hour) for t in ts],
            "rain": [rain(t.hour) for t in ts], "temp": [29] * hours}


@pytest.fixture
def weather(monkeypatch):
    def use(data):
        monkeypatch.setattr("app.services.optimizer.get_forecast", lambda lat, lon: data)
        monkeypatch.setattr("app.services.control.get_forecast", lambda lat, lon: data)
    use(series())
    return use


@pytest.fixture
def plot(app):
    return create_plot("Plot A", "chilli", 1.8548, 103.3345, area_m2=100, num_plants=50)


def reading(plot, simulated=False, **values):
    sensor, _ = create_device(plot, name="probe", simulated=simulated)
    ingest(sensor, [{"ts": utcnow().isoformat() + "+00:00", **values}])


def valve(plot):
    return create_device(plot, simulated=True, kind="valve")[0]


def test_needs_valve_and_moisture(plot, weather):
    assert optimise(plot)["status"] == "no_valve"
    valve(plot)
    assert optimise(plot)["status"] == "no_moisture"


def test_dry_soil_prefers_morning_over_evening(plot, weather):
    valve(plot)
    reading(plot, simulated=True, soil_moisture_pct=18)
    r = optimise(plot)
    assert r["status"] == "ok" and r["simulated_input"] is True and r["placeholder"] is True
    best = r["best"]
    assert best["litres"] > 0 and best["time_local"] in ("06:00", "07:00", "08:00")
    assert best["mean_out_pct"] < r["skip"]["mean_out_pct"]
    codes = {x["code"]: x for x in r["reasons"]}
    assert codes["closer_to_target"]["after"] > codes["closer_to_target"]["before"]
    assert codes["vs_time"]["time"] == "19:00" and codes["vs_time"]["hours"] > best["added_leaf_wet_hours"]
    assert all(c["litres"] <= r["limits"]["water"]["max_command"] for c in r["ranked"])


def test_rain_forecast_means_skip(plot, weather):
    weather(series(rain=lambda h: 3.0, rh=lambda h: 95))
    valve(plot)
    reading(plot, soil_moisture_pct=20)
    r = optimise(plot)
    assert r["best"]["kind"] == "skip"
    assert {x["code"] for x in r["reasons"]} >= {"skip_best", "rain_expected"}
    assert r["excluded"] == r["considered"] - 1


def test_wet_soil_blocks_watering_now(plot, weather):
    valve(plot)
    reading(plot, soil_moisture_pct=46)
    r = optimise(plot)
    assert r["best"]["kind"] == "skip"


def test_daily_limit_excludes_large_amounts(plot, weather):
    v = valve(plot)
    reading(plot, soil_moisture_pct=18)
    db.session.add(DeviceCommand(request_id="x1", plot_id=plot.id, device_id=v.id, action="water", amount=950,
                                 unit="L", source="manual", status="done", created_at=utcnow()))
    db.session.commit()
    today = (utcnow() + timedelta(hours=8)).date().isoformat()
    r = optimise(plot)
    assert all(c["litres"] <= 50 for c in r["ranked"] if c["date_local"] == today)


def test_schedule_is_compared(plot, weather):
    valve(plot)
    reading(plot, soil_moisture_pct=18)
    create_schedule(plot, {"action": "water", "amount": 300, "time_local": "19:00"})
    r = optimise(plot)
    assert len(r["schedules"]) == 1
    s = r["schedules"][0]
    assert s["time_local"] == "19:00" and s["score"] >= r["best"]["score"]


def test_leaf_wetness_from_watering():
    start = datetime(2026, 1, 1, 17)
    w = [(start + timedelta(hours=k), {"rh": 70, "rain": 0}) for k in range(24)]
    cfg = {"irrigation_wets_leaves": True, "max_wet_hours_after_watering": 12, "drying_hours": [7, 18]}
    assert wet_from_watering(w, 0, [False] * 24, cfg) == 12      # 17:00 – dries only next morning (capped)
    assert wet_from_watering(w, 14, [False] * 24, cfg) == 1      # 07:00 – dries within the hour
    assert wet_from_watering(w, 2, [True] * 24, cfg) == 0        # night already wet
    assert wet_from_watering(w, 14, [False] * 24, {**cfg, "irrigation_wets_leaves": False}) == 0


def test_fertiliser_timing(plot, weather):
    assert optimise(plot)["fertilise"]["status"] == "no_doser"
    d = create_device(plot, simulated=True, kind="doser")[0]
    f = optimise(plot)["fertilise"]
    assert f["status"] == "ok" and f["time_local"] in ("07:00", "08:00") and f["last_amount"] is None
    db.session.add(DeviceCommand(request_id="f1", plot_id=plot.id, device_id=d.id, action="fertilise", amount=500,
                                 unit="g", source="manual", status="done", created_at=utcnow() - timedelta(hours=10)))
    db.session.commit()
    f = optimise(plot)["fertilise"]
    if f["status"] == "ok":
        assert f["in_hours"] >= 62 and f["last_amount"] == 500
    else:
        assert f["status"] == "none_in_horizon" and f["earliest"]
    weather(series(rain=lambda h: 2.0))
    assert optimise(plot)["fertilise"]["status"] == "none_in_horizon"
    reading(plot, soil_ec_ds_m=3.0)
    assert optimise(plot)["fertilise"]["status"] == "ec_high"


def test_optimise_api(client, plot, weather):
    login(client, "farmer")
    assert client.get(f"/api/plots/{plot.id}/optimise").status_code == 404
    plot.owner_id = User.query.filter_by(username="farmer").one().id
    db.session.commit()
    body = client.get(f"/api/plots/{plot.id}/optimise").get_json()
    assert body["can_control"] is True and body["status"] == "no_valve"
