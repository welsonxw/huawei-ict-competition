"""Phase 10: Huawei Cloud IoTDA / MQTT adapters. Both feed the same ingest() as the HTTP endpoint.

Devices speak the IoTDA device-side MQTT topics, so the same firmware works against a local Mosquitto broker
(dev, via `flask mqtt-bridge`) and against IoTDA (cloud, via an HTTP data-forwarding rule to /api/iot/iotda/push).

  device -> $oc/devices/{device_id}/sys/properties/report
            {"services": [{"service_id": "Sensor", "properties": {"soil_moisture_pct": 31.5, ...},
                           "event_time": "20260101T080000Z"}]}

IoTDA device_id = "{product_id}_{node_id}"; we register node_id = our Device.uid.
Formats: IoTDA API reference "Push a Device Property Reporting Notification" and device-side
"Reporting Device Properties" (support.huaweicloud.com).
"""
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone

from flask import current_app

from ..models import Device
from .iot import IoTError, ingest

REPORT_TOPIC = "$oc/devices/+/sys/properties/report"
_TOPIC_RE = re.compile(r"^\$oc/devices/([^/]+)/sys/properties/report$")


def _event_time(value):
    """IoTDA 'yyyyMMddTHHmmssZ' (UTC) -> ISO string accepted by parse_reading; None -> server time."""
    if not value:
        return None
    try:
        ts = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise IoTError(f"invalid event_time: {value!r}") from exc
    return ts.isoformat()


def readings_from_services(services):
    """Merge IoTDA service properties into one reading per event_time."""
    if not isinstance(services, list) or not services:
        raise IoTError("services must be a non-empty list")
    by_time = {}
    for svc in services:
        if not isinstance(svc, dict) or not isinstance(svc.get("properties"), dict):
            raise IoTError("each service needs a properties object")
        key = svc.get("event_time")
        by_time.setdefault(key, {}).update(svc["properties"])
    readings = []
    for key, props in by_time.items():
        reading = {k: v for k, v in props.items() if k != "ts"}
        reading["ts"] = _event_time(key)
        readings.append(reading)
    return readings


def uid_from_device_id(device_id):
    """IoTDA device_id '{product_id}_{node_id}' -> node_id (= Device.uid). Plain uids pass through (local broker)."""
    product = current_app.config.get("IOTDA_PRODUCT_ID") or ""
    if product and device_id.startswith(product + "_"):
        return device_id[len(product) + 1:]
    return device_id


def find_device(device_id=None, node_id=None):
    uid = node_id or (uid_from_device_id(device_id) if device_id else None)
    return Device.query.filter_by(uid=uid).first() if uid else None


def check_push_token(token):
    expected = current_app.config.get("IOTDA_PUSH_TOKEN") or ""
    return bool(expected) and bool(token) and hmac.compare_digest(expected, token)


def handle_push(body):
    """IoTDA data-forwarding notification (resource=device.property, event=report). Returns (device, rows)."""
    if not isinstance(body, dict):
        raise IoTError("body must be an object")
    if (body.get("resource"), body.get("event")) != ("device.property", "report"):
        raise IoTError("only device.property/report notifications are accepted")
    data = body.get("notify_data") or {}
    header, payload = data.get("header") or {}, data.get("body") or {}
    device = find_device(header.get("device_id"), header.get("node_id"))
    if device is None:
        raise LookupError("unknown device")
    return device, ingest(device, readings_from_services(payload.get("services")), transport="iotda")


def handle_mqtt_message(topic, payload):
    """One MQTT property report from the local broker. Returns (device, rows)."""
    match = _TOPIC_RE.match(topic)
    if not match:
        raise IoTError(f"unexpected topic {topic!r}")
    device = find_device(match.group(1))
    if device is None:
        raise LookupError("unknown device")
    try:
        body = json.loads(payload)
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise IoTError("payload is not JSON") from exc
    if not isinstance(body, dict):
        raise IoTError("payload must be an object")
    return device, ingest(device, readings_from_services(body.get("services")), transport="mqtt")


def device_mqtt_credentials(device_id, secret, now=None):
    """IoTDA MQTT CONNECT credentials: ClientId {device_id}_0_0_{YYYYMMDDHH}, password HMAC-SHA256(secret, key=ts)."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d%H")
    password = hmac.new(stamp.encode(), secret.encode(), hashlib.sha256).hexdigest()
    return f"{device_id}_0_0_{stamp}", device_id, password
