import json
from datetime import datetime, timedelta, timezone

import pytest
from app.models import SensorReading
from app.models.core import utcnow
from app.services.iot import IoTError, create_device
from app.services.iotda import device_mqtt_credentials, handle_mqtt_message, readings_from_services
from app.services.mqtt_bridge import parse_broker_url
from app.services.scans import create_plot

TOKEN = "t" * 32


@pytest.fixture
def device(app):
    app.config.update(IOTDA_PRODUCT_ID="prod123", IOTDA_PUSH_TOKEN=TOKEN)
    plot = create_plot("Plot A", "chilli", 1.8548, 103.3345)
    return create_device(plot)[0]


def stamp(dt=None):
    return (dt or utcnow()).strftime("%Y%m%dT%H%M%SZ")


def push_body(device_id, node_id, services, resource="device.property"):
    return {"resource": resource, "event": "report", "event_time": stamp(),
            "notify_data": {"header": {"device_id": device_id, "node_id": node_id, "product_id": "prod123"},
                            "body": {"services": services}}}


def test_readings_merge_services_by_event_time():
    t = stamp()
    out = readings_from_services([
        {"service_id": "Soil", "properties": {"soil_moisture_pct": 30}, "event_time": t},
        {"service_id": "Air", "properties": {"air_temp_c": 28}, "event_time": t},
    ])
    assert len(out) == 1 and out[0]["soil_moisture_pct"] == 30 and out[0]["air_temp_c"] == 28
    assert out[0]["ts"].endswith("+00:00")
    with pytest.raises(IoTError):
        readings_from_services([])
    with pytest.raises(IoTError):
        readings_from_services([{"properties": {"air_temp_c": 1}, "event_time": "yesterday"}])


def test_iotda_push_requires_token(client, device):
    body = push_body(f"prod123_{device.uid}", device.uid, [{"properties": {"soil_moisture_pct": 31}}])
    assert client.post("/api/iot/iotda/push/wrong", json=body).status_code == 404
    res = client.post(f"/api/iot/iotda/push/{TOKEN}", json=body)
    assert res.status_code == 200 and res.get_json()["accepted"] == 1
    assert device.transport == "iotda" and SensorReading.query.one().is_simulated is False


def test_iotda_push_disabled_without_configured_token(client, device, app):
    app.config["IOTDA_PUSH_TOKEN"] = ""
    body = push_body("x", device.uid, [{"properties": {"soil_moisture_pct": 31}}])
    assert client.post("/api/iot/iotda/push/", json=body).status_code == 404
    assert client.post("/api/iot/iotda/push/anything", json=body).status_code == 404


def test_iotda_push_rejects_bad_payloads_without_storing(client, device):
    url = f"/api/iot/iotda/push/{TOKEN}"
    cases = [
        push_body("prod123_nope", "nope", [{"properties": {"soil_moisture_pct": 31}}]),
        push_body(device.uid, device.uid, [{"properties": {"soil_moisture_pct": 31}}], resource="device.message"),
        push_body(device.uid, device.uid, [{"properties": {"soil_moisture_pct": 150}}]),
        push_body(device.uid, device.uid, [{"properties": {"air_temp_c": 30},
                                            "event_time": stamp(utcnow() + timedelta(hours=2))}]),
    ]
    for body in cases:
        res = client.post(url, json=body)
        assert res.status_code == 200 and res.get_json()["accepted"] == 0, body
    assert SensorReading.query.count() == 0


def test_iotda_push_resolves_device_id_without_node_id(client, device):
    body = push_body(f"prod123_{device.uid}", None, [{"properties": {"air_temp_c": 29}}])
    assert client.post(f"/api/iot/iotda/push/{TOKEN}", json=body).get_json()["accepted"] == 1


def test_mqtt_message_uses_ingest(device):
    topic = f"$oc/devices/prod123_{device.uid}/sys/properties/report"
    payload = json.dumps({"services": [{"properties": {"soil_moisture_pct": 22, "leaf_wet": True},
                                        "event_time": stamp()}]})
    dev, rows = handle_mqtt_message(topic, payload.encode())
    assert dev.id == device.id and len(rows) == 1 and rows[0].leaf_wet is True
    assert device.transport == "mqtt"
    with pytest.raises(LookupError):
        handle_mqtt_message("$oc/devices/ghost/sys/properties/report", payload)
    with pytest.raises(IoTError):
        handle_mqtt_message(topic, b"not json")
    with pytest.raises(IoTError):
        handle_mqtt_message(f"$oc/devices/{device.uid}/sys/events/up", payload)


def test_iotda_mqtt_credentials_format():
    now = datetime(2018, 7, 24, 17, 56, 20, tzinfo=timezone.utc)
    client_id, username, password = device_mqtt_credentials("prod_tg-1-ab", "secret", now)
    assert client_id == "prod_tg-1-ab_0_0_2018072417" and username == "prod_tg-1-ab"
    assert len(password) == 64 and password != "secret"
    # worked example from the IoTDA device-authentication API reference
    _, _, documented = device_mqtt_credentials("d", "12345678", datetime(2025, 4, 14, 1, tzinfo=timezone.utc))
    assert documented == "c75150e6cb841417396819e4d2ee4358a416344a03a083e3a8567074ddec820a"


def test_parse_broker_url():
    assert parse_broker_url("mqtt://mosquitto") == ("mosquitto", 1883, False)
    assert parse_broker_url("mqtts://iot.example:8883") == ("iot.example", 8883, True)
    with pytest.raises(ValueError):
        parse_broker_url("http://x")


def test_system_reports_iot_transport(client, app):
    assert client.get("/api/system").get_json()["iot"] == "http"
    app.config["MQTT_BROKER_URL"] = "mqtt://mosquitto:1883"
    assert client.get("/api/system").get_json()["iot"] == "mqtt"
    app.config["IOTDA_PUSH_TOKEN"] = TOKEN
    assert client.get("/api/system").get_json()["iot"] == "iotda"
