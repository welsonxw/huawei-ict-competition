"""Stand-alone "Simulated device": posts readings to /api/iot/readings exactly like a real ESP32 would.

    flask add-device 1 --simulated          # prints a device ID and one-time key
    python scripts/device_simulator.py --url http://localhost:8080 \\
        --device tg-1-abcd1234 --key <key> --lat 1.8548 --lon 103.3345 [--interval 60] [--speed 60]

Uses the same soil/air model as the in-app simulator, driven by the Open-Meteo forecast (or a synthetic
day/night pattern when offline). Readings are generated, not measured: register the device with
--simulated so the app labels it "Simulated device". A real ESP32 uses the same endpoint and headers.
"""
import argparse
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

from app.services.device_sim import initial_state, step, weather_at, weather_lookup  # noqa: E402
from app.services.weather import fetch_open_meteo  # noqa: E402


def load_yaml(name):
    with open(ROOT / "config" / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8080")
    parser.add_argument("--device", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--interval", type=float, default=60, help="seconds between posts (wall clock)")
    parser.add_argument("--speed", type=float, default=1, help="simulated seconds per wall-clock second")
    parser.add_argument("--count", type=int, default=0, help="stop after N posts (0 = run forever)")
    args = parser.parse_args()

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
        body = {**reading}
        if args.speed == 1:
            body["ts"] = sim_now.isoformat() + "+00:00"
        res = requests.post(f"{args.url}/api/iot/readings", json=body, timeout=15,
                            headers={"X-Device-Id": args.device, "X-Device-Key": args.key})
        print(local.strftime("%d %b %H:%M"), res.status_code, reading)
        sent += 1
        sim_now += dt
        if not args.count or sent < args.count:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
