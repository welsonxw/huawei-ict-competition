"""Sensor devices and readings (Phase 9). Same ingest path for simulated devices now and MQTT/IoTDA later."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from ..extensions import db
from ..models import Device, Plot, SensorReading
from ..models.core import utcnow
from .config_loader import iot as iot_config

SIMULATED_DEVICE_LABEL = "Simulated device"


class IoTError(ValueError):
    pass


def _hash_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


EXTERNAL_SIM_KIND = "sim-external"


def create_device(plot, name=None, simulated=False, external=False):
    """Register a device on a plot. Returns (device, plain_key); the key is only ever shown once.

    external=True marks a simulated device driven by scripts/device_simulator.py over HTTP
    rather than by the in-app scheduler; it is still labelled "Simulated device"."""
    key = secrets.token_urlsafe(24)
    device = Device(
        uid=f"tg-{plot.id}-{secrets.token_hex(4)}",
        plot_id=plot.id,
        name=(name or "").strip()[:80] or (f"{SIMULATED_DEVICE_LABEL} – {plot.name}" if simulated else f"Sensor – {plot.name}"),
        key_hash=_hash_key(key),
        kind=EXTERNAL_SIM_KIND if simulated and external else "sensor",
        is_simulated=bool(simulated),
    )
    db.session.add(device)
    db.session.commit()
    return device, key


def authenticate_device(uid, key):
    if not uid or not key:
        return None
    device = Device.query.filter_by(uid=uid).first()
    if device and hmac.compare_digest(device.key_hash, _hash_key(key)):
        return device
    return None


def _parse_ts(value, now):
    cfg = iot_config()
    if value in (None, ""):
        return now
    try:
        if isinstance(value, (int, float)):
            ts = datetime.fromtimestamp(float(value), tz=timezone.utc)
        else:
            ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError) as exc:
        raise IoTError(f"invalid ts: {value!r}") from exc
    if ts.tzinfo is None:
        raise IoTError("ts must include a timezone (e.g. 2026-01-01T08:00:00Z)")
    ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
    if ts > now + timedelta(minutes=cfg["max_future_minutes"]):
        raise IoTError("ts is in the future")
    if ts < now - timedelta(hours=cfg["max_backfill_hours"]):
        raise IoTError("ts is too old")
    return ts


def parse_reading(payload, now=None):
    """Validate one reading dict -> column values. Raises IoTError."""
    if not isinstance(payload, dict):
        raise IoTError("reading must be an object")
    now = now or utcnow()
    cfg = iot_config()["metrics"]
    values = {"ts": _parse_ts(payload.get("ts"), now)}
    for metric, spec in cfg.items():
        raw = payload.get(metric)
        if raw is None:
            continue
        if spec.get("bool"):
            if not isinstance(raw, (bool, int)) or raw not in (0, 1, True, False):
                raise IoTError(f"{metric} must be true/false")
            values[metric] = bool(raw)
            continue
        if isinstance(raw, bool):
            raise IoTError(f"{metric} must be a number")
        try:
            val = float(raw)
        except (TypeError, ValueError) as exc:
            raise IoTError(f"{metric} must be a number") from exc
        if val != val or not spec["min"] <= val <= spec["max"]:
            raise IoTError(f"{metric} out of range [{spec['min']}, {spec['max']}]")
        values[metric] = round(val, 2)
    if len(values) == 1:
        raise IoTError("reading has no sensor values")
    return values


def ingest(device, payloads, now=None):
    """Store one or many readings for a device (all-or-nothing). Returns the new rows."""
    if isinstance(payloads, dict):
        payloads = [payloads]
    if not isinstance(payloads, list) or not payloads:
        raise IoTError("no readings")
    if len(payloads) > iot_config()["max_batch"]:
        raise IoTError(f"at most {iot_config()['max_batch']} readings per request")
    now = now or utcnow()
    parsed = [parse_reading(p, now) for p in payloads]
    rows = [SensorReading(device_id=device.id, plot_id=device.plot_id, is_simulated=device.is_simulated, **v)
            for v in parsed]
    db.session.add_all(rows)
    latest = max(r.ts for r in rows)
    if not device.last_seen_at or latest > device.last_seen_at:
        device.last_seen_at = latest
    db.session.commit()
    return rows


def _status(value, band):
    if value is None or band is None:
        return None
    lo, hi = band
    if lo is not None and value < lo:
        return "low"
    if hi is not None and value > hi:
        return "high"
    return "ok"


def _wet_hours(readings):
    """Hours leaves have been continuously wet up to the latest reading (readings sorted ascending)."""
    end = start = None
    for r in reversed(readings):
        if r.leaf_wet is None:
            continue
        if not r.leaf_wet:
            break
        end = end or r.ts
        start = r.ts
    return round((end - start).total_seconds() / 3600, 1) if end else 0.0


def monitor(plot, hours=24, now=None):
    """Live status of a plot: latest values, target status, alerts and history."""
    cfg = iot_config()
    now = now or utcnow()
    hours = max(1, min(int(hours), cfg["max_backfill_hours"]))
    devices = Device.query.filter_by(plot_id=plot.id).order_by(Device.id).all()
    readings = (SensorReading.query.filter(SensorReading.plot_id == plot.id,
                                           SensorReading.ts >= now - timedelta(hours=hours))
                .order_by(SensorReading.ts).all())
    latest = {}
    for r in readings:
        for m in SensorReading.METRICS:
            if getattr(r, m) is not None:
                latest[m] = {"value": getattr(r, m), "ts": r.ts.isoformat() + "Z"}
    targets = cfg["targets"].get(plot.crop, {})
    status = {m: _status(latest[m]["value"], targets.get(m)) for m in latest if m in targets}

    offline_after = timedelta(minutes=cfg["offline_minutes"])
    device_rows = []
    alerts = []
    for d in devices:
        online = bool(d.last_seen_at and now - d.last_seen_at <= offline_after)
        device_rows.append({**d.to_dict(), "online": online})
        if not online:
            alerts.append({"code": "offline", "level": "warn", "device": d.name,
                           "last_seen_at": device_rows[-1]["last_seen_at"]})
    for metric, st in status.items():
        if st in ("low", "high"):
            alerts.append({"code": f"{metric}_{st}", "level": "warn", "metric": metric,
                           "value": latest[metric]["value"], "band": targets[metric]})
    wet = _wet_hours(readings)
    if wet >= cfg["leaf_wet_alert_hours"]:
        alerts.append({"code": "leaf_wet_long", "level": "danger", "hours": wet})
    batt = latest.get("battery_pct")
    if batt and batt["value"] < cfg["low_battery_pct"]:
        alerts.append({"code": "battery_low", "level": "warn", "value": batt["value"]})

    simulated = any(d.is_simulated for d in devices)
    return {
        "plot": plot.to_dict(),
        "hours": hours,
        "devices": device_rows,
        "latest": latest,
        "status": status,
        "targets": targets,
        "targets_placeholder": bool(cfg.get("placeholder")),
        "leaf_wet_hours": wet,
        "alerts": alerts,
        "history": [r.to_dict() for r in readings],
        "units": {m: s.get("unit", "") for m, s in cfg["metrics"].items()},
        "simulated": simulated,
        "label": SIMULATED_DEVICE_LABEL if simulated else None,
        "generated_at": now.isoformat() + "Z",
    }


def get_plot(plot_id):
    return db.session.get(Plot, plot_id)
