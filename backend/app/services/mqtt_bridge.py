"""Local MQTT bridge (`flask mqtt-bridge`): subscribes to IoTDA-style property reports on a broker such as
Mosquitto and stores them through the normal ingest path. On Huawei Cloud, IoTDA forwards to
/api/iot/iotda/push instead, so this process is only needed for local development or a self-hosted broker."""
import json
import logging
from urllib.parse import urlparse

import paho.mqtt.client as mqtt

from ..extensions import db
from .iot import IoTError
from .control import record_response
from .iotda import REPORT_TOPIC, handle_mqtt_message

log = logging.getLogger(__name__)
RESPONSE_TOPIC = "$oc/devices/+/sys/commands/response/#"


def parse_broker_url(url):
    u = urlparse(url)
    if u.scheme not in ("mqtt", "mqtts") or not u.hostname:
        raise ValueError("MQTT_BROKER_URL must look like mqtt://host:1883 or mqtts://host:8883")
    return u.hostname, u.port or (8883 if u.scheme == "mqtts" else 1883), u.scheme == "mqtts"


def handle_command_response(topic, payload):
    """$oc/devices/{uid}/sys/commands/response/request_id={id} -> acknowledge the DeviceCommand."""
    parts = topic.split("/")
    if len(parts) != 7 or parts[3:6] != ["sys", "commands", "response"] or not parts[6].startswith("request_id="):
        return None
    from ..models import Device

    device = Device.query.filter_by(uid=parts[2]).first()
    if device is None:
        return None
    try:
        body = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        body = {"result_code": 1}
    return record_response(parts[6].removeprefix("request_id="), body, device=device)


def on_message_factory(app):
    def on_message(client, userdata, msg):
        with app.app_context():
            if "/sys/commands/response/" in msg.topic:
                cmd = handle_command_response(msg.topic, msg.payload)
                log.info("mqtt %s: %s", msg.topic, f"command {cmd.status}" if cmd else "unknown command")
                return
            try:
                device, rows = handle_mqtt_message(msg.topic, msg.payload)
                log.info("mqtt %s: stored %d reading(s)", device.uid, len(rows))
            except LookupError:
                log.warning("mqtt %s: unknown device", msg.topic)
            except IoTError as exc:
                db.session.rollback()
                log.warning("mqtt %s: rejected (%s)", msg.topic, exc)
    return on_message


def run_bridge(app):
    cfg = app.config
    host, port, tls = parse_broker_url(cfg["MQTT_BROKER_URL"])
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="taniguard-bridge")
    if cfg.get("MQTT_USERNAME"):
        client.username_pw_set(cfg["MQTT_USERNAME"], cfg.get("MQTT_PASSWORD") or None)
    if tls:
        client.tls_set()

    def on_connect(client, userdata, flags, reason_code, properties):
        log.info("connected to %s:%s (%s); subscribing %s, %s", host, port, reason_code, REPORT_TOPIC, RESPONSE_TOPIC)
        client.subscribe([(REPORT_TOPIC, 1), (RESPONSE_TOPIC, 1)])

    client.on_connect = on_connect
    client.on_message = on_message_factory(app)
    client.connect(host, port, keepalive=60)
    client.loop_forever(retry_first_connection=True)
