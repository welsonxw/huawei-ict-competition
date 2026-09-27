"""Stand-alone "Simulated device": posts readings to /api/iot/readings exactly like a real ESP32 would.

    flask add-device 1 --simulated          # prints a device ID and one-time key
    python scripts/device_simulator.py --url http://localhost:8080 \\
        --device tg-1-abcd1234 --key <key> --lat 1.8548 --lon 103.3345 [--interval 60] [--speed 60]

MQTT mode (Phase 10) publishes IoTDA-format property reports instead of HTTP posts:

    # local Mosquitto (docker compose --profile iot up)
    python scripts/device_simulator.py --mqtt mqtt://localhost:1883 --device tg-1-abcd1234 --lat ... --lon ...
    # Huawei Cloud IoTDA (device registered with node_id = tg-1-abcd1234, secret = the device key)
    python scripts/device_simulator.py --mqtt mqtts://<iotda-host>:8883 --iotda-product <product_id> \
        --device tg-1-abcd1234 --key <key> --lat ... --lon ...

Uses the same soil/air model as the in-app simulator, driven by the Open-Meteo forecast (or a synthetic
day/night pattern when offline). Readings are generated, not measured: register the device with
--simulated so the app labels it "Simulated device". A real ESP32 uses the same endpoint and headers.
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

from app.services.device_sim import initial_state, step, weather_at, weather_lookup  # noqa: E402
from app.services.iotda import device_mqtt_credentials  # noqa: E402
from app.services.mqtt_bridge import parse_broker_url  # noqa: E402
from app.services.weather import fetch_open_meteo  # noqa: E402


def iotda_report(reading, ts):
    return {"services": [{"service_id": "Sensor", "properties": reading, "event_time": ts.strftime("%Y%m%dT%H%M%SZ")}]}


def mqtt_client(url, device_id, key):
    host, port, tls = parse_broker_url(url)
    if key:
        client_id, username, password = device_mqtt_credentials(device_id, key)
    else:
        client_id, username, password = device_id, None, None
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if username:
        client.username_pw_set(username, password)
    if tls:
        client.tls_set()
    client.connect(host, port, keepalive=60)
    client.loop_start()
    return client


def load_yaml(name):
    with open(ROOT / "config" / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--device", required=True)
    parser.add_argument("--key", help="device key (HTTP) / IoTDA device secret (MQTT to IoTDA)")
    parser.add_argument("--mqtt", help="broker URL, e.g. mqtt://localhost:1883; publish IoTDA-format reports")
    parser.add_argument("--iotda-product", default="", help="IoTDA product ID; device_id becomes <product>_<device>")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--interval", type=float, default=60, help="seconds between posts (wall clock)")
    parser.add_argument("--speed", type=float, default=1, help="simulated seconds per wall-clock second")
    parser.add_argument("--count", type=int, default=0, help="stop after N posts (0 = run forever)")
    args = parser.parse_args()
    if not args.mqtt and not args.key:
        parser.error("--key is required for HTTP mode")
    device_id = f"{args.iotda_product}_{args.device}" if args.iotda_product else args.device
    client = mqtt_client(args.mqtt, device_id, args.key if args.iotda_product else None) if args.mqtt else None

    cfg = load_yaml("iot.yaml")["simulator"]
    wcfg = load_yaml("thresholds.yaml")["weather"]
    try:
        lookup = weather_lookup(fetch_open_meteo(args.lat, args.lon))
    except requests.RequestException as exc:
        print(f"weather unavailable ({exc}); using synthetic day/night pattern")
        lookup = {}
    state = initial_state(cfg)
    sim_now = datetime.now(timezone.utc).replace(tzinfo=None)
    dt = timedelta(seconds=args.interval * args.speed)
    sent = 0
    while not args.count or sent < args.count:
        weather, local = weather_at(lookup, sim_now)
        rng = random.Random(f"{args.device}|{sim_now.isoformat()}")
        model, reading = step(state, weather, local, dt.total_seconds() / 3600, cfg,
                              wcfg["leaf_wetness_rh"], wcfg["rain_mm_threshold"], rng)
        state.update(model)
        ts = sim_now if args.speed == 1 else datetime.now(timezone.utc).replace(tzinfo=None)
        if client:
            info = client.publish(f"$oc/devices/{device_id}/sys/properties/report",
                                  json.dumps(iotda_report(reading, ts)), qos=1)
            info.wait_for_publish(timeout=15)
            status = "published" if info.is_published() else "not published"
        else:
            body = {**reading}
            if args.speed == 1:
                body["ts"] = sim_now.isoformat() + "+00:00"
            status = requests.post(f"{args.url}/api/iot/readings", json=body, timeout=15,
                                   headers={"X-Device-Id": args.device, "X-Device-Key": args.key}).status_code
        print(local.strftime("%d %b %H:%M"), status, reading)
        sent += 1
        sim_now += dt
        if not args.count or sent < args.count:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
