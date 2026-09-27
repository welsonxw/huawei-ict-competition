"""Watering / fertiliser control (Phase 11): safety checks, confirmation, dispatch, acknowledgement, schedules.

Lifecycle of a DeviceCommand:
  awaiting_confirmation -> sent -> done | failed | expired
                        -> blocked (safety re-check failed at confirm time) | cancelled | expired
  blocked (a blocking check failed when requested; logged, cannot be confirmed)
Scheduled commands skip the confirm step (creating the schedule was the confirmation) but run the same checks.
"""
import json
import logging
import uuid
from datetime import date, datetime, timedelta

import requests
from flask import current_app

from ..extensions import db
from ..models import ControlSchedule, Device, DeviceCommand, SensorReading
from ..models.core import utcnow
from .config_loader import iot as iot_config
from .config_loader import load_config
from .config_loader import thresholds
from .iot import ACTUATOR_KINDS, SENSOR_KIND, ingest
from .weather import get_forecast, summarise

log = logging.getLogger(__name__)

ACTIONS = ("water", "fertilise")
SOURCES = ("manual", "schedule", "game", "optimizer")
KIND_FOR_ACTION = {action: kind for kind, action in ACTUATOR_KINDS.items()}
OPEN = ("awaiting_confirmation", "sent")
USED = ("sent", "done")
MYT = timedelta(hours=8)


class ControlError(ValueError):
    pass


def control_config():
    return load_config("control.yaml")


def local_now(now=None):
    return (now or utcnow()) + MYT


def plot_area(plot, cfg=None):
    cfg = cfg or control_config()
    return plot.area_m2 if plot.area_m2 and plot.area_m2 > 0 else cfg["default_area_m2"]


def limits(plot, cfg=None):
    """Per-plot absolute limits (per-m² defaults x area) shown in the UI and enforced by the checks."""
    cfg = cfg or control_config()
    area = plot_area(plot, cfg)
    w, f = cfg["water"], cfg["fertilise"]
    targets = iot_config()["targets"].get(plot.crop, {})
    wet = w["skip_if_moisture_pct_at_least"]
    if wet is None:
        wet = (targets.get("soil_moisture_pct") or [None, None])[1]
    ec = f["block_if_ec_at_least"]
    if ec is None:
        ec = (targets.get("soil_ec_ds_m") or [None, None])[1]
    return {
        "area_m2": area,
        "area_is_default": not (plot.area_m2 and plot.area_m2 > 0),
        "water": {"unit": w["unit"], "max_command": round(w["max_l_per_m2_command"] * area, 1),
                  "max_day": round(w["max_l_per_m2_day"] * area, 1), "skip_moisture_pct": wet,
                  "rain_skip_mm": w["rain_skip_mm"], "rain_window_hours": w["rain_window_hours"],
                  "flow_l_per_min": w["flow_l_per_min"]},
        "fertilise": {"unit": f["unit"], "max_command": round(f["max_g_per_m2_command"] * area, 1),
                      "max_day": round(f["max_g_per_m2_day"] * area, 1), "min_hours_between": f["min_hours_between"],
                      "block_ec": ec},
        "placeholder": bool(cfg.get("placeholder")),
    }


def actuators(plot):
    return (Device.query.filter(Device.plot_id == plot.id, Device.kind.in_(tuple(ACTUATOR_KINDS)))
            .order_by(Device.id).all())


def pick_actuator(plot, action, device_id=None):
    kind = KIND_FOR_ACTION[action]
    q = Device.query.filter_by(plot_id=plot.id, kind=kind)
    device = q.filter_by(id=device_id).first() if device_id is not None else q.order_by(Device.id).first()
    if device is None:
        raise ControlError("no valve on this plot" if action == "water" else "no fertiliser doser on this plot")
    return device


def _latest(plot, metric, max_age, now):
    col = getattr(SensorReading, metric)
    r = (SensorReading.query.filter(SensorReading.plot_id == plot.id, col.isnot(None),
                                    SensorReading.ts >= now - max_age, SensorReading.ts <= now + timedelta(minutes=5))
         .order_by(SensorReading.ts.desc()).first())
    return getattr(r, metric) if r else None


def _used_today(plot, action, now):
    start_local = datetime.combine(local_now(now).date(), datetime.min.time())
    start = start_local - MYT
    rows = DeviceCommand.query.filter(DeviceCommand.plot_id == plot.id, DeviceCommand.action == action,
                                      DeviceCommand.status.in_(USED), DeviceCommand.created_at >= start).all()
    return round(sum(r.amount for r in rows), 1)


def _last_done(plot, action):
    return (DeviceCommand.query.filter(DeviceCommand.plot_id == plot.id, DeviceCommand.action == action,
                                       DeviceCommand.status.in_(USED))
            .order_by(DeviceCommand.created_at.desc()).first())


def _device_online(device, now):
    if device.is_simulated:
        return True
    window = timedelta(minutes=iot_config()["offline_minutes"])
    return bool(device.last_seen_at and now - device.last_seen_at <= window)


def rain_forecast_mm(plot, hours, now):
    wcfg = thresholds()["weather"]
    try:
        forecast = get_forecast(plot.lat, plot.lon)
    except Exception:  # noqa: BLE001
        log.warning("forecast unavailable for control check", exc_info=True)
        forecast = None
    summary = summarise(forecast, hours, wcfg["rain_mm_threshold"], wcfg["leaf_wetness_rh"], now=local_now(now))
    return None if summary is None else summary["total_rain_mm"]


def check(level, code, **values):
    return {"level": level, "code": code, "vars": values}


def evaluate(plot, device, action, amount, now=None, exclude_id=None):
    """Safety checks for one command. Returns a list of {level: block|warn|ok, code, vars}."""
    now = now or utcnow()
    cfg = control_config()
    lim = limits(plot, cfg)[action]
    unit = lim["unit"]
    out = []
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        return [check("block", "amount_invalid")]
    if amount > lim["max_command"]:
        out.append(check("block", "amount_over_command", amount=amount, max=lim["max_command"], unit=unit))
    if not _device_online(device, now):
        out.append(check("block", "device_offline", device=device.name))
    busy = DeviceCommand.query.filter(DeviceCommand.device_id == device.id, DeviceCommand.status == "sent")
    if exclude_id is not None:
        busy = busy.filter(DeviceCommand.id != exclude_id)
    if busy.first():
        out.append(check("block", "device_busy", device=device.name))
    used = _used_today(plot, action, now)
    if used + amount > lim["max_day"]:
        out.append(check("block", f"{action}_daily_limit", used=used, amount=amount, max=lim["max_day"], unit=unit))
    else:
        out.append(check("ok", f"{action}_daily_ok", used=used, amount=amount, max=lim["max_day"], unit=unit))

    if action == "water":
        w = cfg["water"]
        moisture = _latest(plot, "soil_moisture_pct", timedelta(minutes=w["moisture_max_age_minutes"]), now)
        if moisture is None:
            out.append(check("warn", "moisture_unknown"))
        elif lim["skip_moisture_pct"] is not None and moisture >= lim["skip_moisture_pct"]:
            out.append(check("block", "moisture_high", value=moisture, limit=lim["skip_moisture_pct"]))
        else:
            out.append(check("ok", "moisture_ok", value=moisture, limit=lim["skip_moisture_pct"]))
        rain = rain_forecast_mm(plot, w["rain_window_hours"], now)
        if rain is None:
            out.append(check("warn", "forecast_unknown"))
        elif rain >= w["rain_skip_mm"]:
            out.append(check("block", "rain_forecast", mm=rain, hours=w["rain_window_hours"]))
        else:
            out.append(check("ok", "rain_ok", mm=rain, hours=w["rain_window_hours"]))
        if local_now(now).hour >= w["evening_warn_from_hour"]:
            out.append(check("warn", "evening_watering", hour=w["evening_warn_from_hour"]))
    else:
        f = cfg["fertilise"]
        last = _last_done(plot, "fertilise")
        if last is not None:
            hours = (now - last.created_at).total_seconds() / 3600
            if hours < f["min_hours_between"]:
                out.append(check("block", "fertilise_too_soon", hours=round(hours, 1), min=f["min_hours_between"]))
        ec = _latest(plot, "soil_ec_ds_m", timedelta(minutes=cfg["water"]["moisture_max_age_minutes"]), now)
        if ec is None:
            out.append(check("warn", "ec_unknown"))
        elif lim["block_ec"] is not None and ec >= lim["block_ec"]:
            out.append(check("block", "ec_high", value=ec, limit=lim["block_ec"]))
        else:
            out.append(check("ok", "ec_ok", value=ec, limit=lim["block_ec"]))
        rain = rain_forecast_mm(plot, f["rain_window_hours"], now)
        if rain is not None and rain >= f["rain_warn_mm"]:
            out.append(check("warn", "fertilise_rain", mm=rain, hours=f["rain_window_hours"]))
    return out


def blocked(checks):
    return any(c["level"] == "block" for c in checks)


def _params(action, amount, cfg):
    if action == "water":
        return {"litres": amount, "duration_s": int(round(amount / cfg["water"]["flow_l_per_min"] * 60))}
    return {"grams": amount}


def request_command(plot, action, amount, user=None, device_id=None, source="manual", schedule=None, now=None):
    """Create a command. Manual/game/optimizer commands wait for confirmation; scheduled ones dispatch at once."""
    if action not in ACTIONS:
        raise ControlError(f"action must be one of {', '.join(ACTIONS)}")
    if source not in SOURCES:
        raise ControlError(f"source must be one of {', '.join(SOURCES)}")
    now = now or utcnow()
    cfg = control_config()
    device = pick_actuator(plot, action, device_id)
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ControlError("amount must be a number") from None
    checks = evaluate(plot, device, action, amount, now)
    cmd = DeviceCommand(
        request_id=uuid.uuid4().hex, plot_id=plot.id, device_id=device.id, action=action, amount=amount,
        unit=cfg[action]["unit"], params=_params(action, amount, cfg), source=source, checks=checks,
        is_simulated=device.is_simulated, requested_by=user.id if user else None,
        schedule_id=schedule.id if schedule else None, created_at=now,
    )
    if blocked(checks):
        cmd.status = "blocked"
    elif source == "schedule":
        cmd.status = "awaiting_confirmation"
        cmd.confirmed_at = now
    else:
        cmd.status = "awaiting_confirmation"
        cmd.expires_at = now + timedelta(minutes=cfg["confirm_window_minutes"])
    db.session.add(cmd)
    db.session.commit()
    if source == "schedule" and cmd.status == "awaiting_confirmation":
        dispatch(cmd, now)
    return cmd


def confirm_command(cmd, now=None):
    now = now or utcnow()
    expire_stale(now)
    if cmd.status != "awaiting_confirmation":
        raise ControlError(f"command is {cmd.status}")
    checks = evaluate(cmd.plot, cmd.device, cmd.action, cmd.amount, now, exclude_id=cmd.id)
    cmd.checks = checks
    cmd.confirmed_at = now
    if blocked(checks):
        cmd.status = "blocked"
        db.session.commit()
        return cmd
    db.session.commit()
    return dispatch(cmd, now)


def cancel_command(cmd, now=None):
    if cmd.status != "awaiting_confirmation":
        raise ControlError(f"command is {cmd.status}")
    cmd.status = "cancelled"
    cmd.completed_at = now or utcnow()
    db.session.commit()
    return cmd


def command_payload(cmd):
    """IoTDA-format command body (service_id, command_name, paras)."""
    spec = control_config()["commands"][cmd.action]
    return {"service_id": spec["service_id"], "command_name": spec["command_name"], "paras": cmd.params or {}}


def transport_for(device):
    cfg = current_app.config
    if device.is_simulated and device.kind in ACTUATOR_KINDS:
        return "sim"
    if device.transport == "iotda" and cfg["IOTDA_API_ENDPOINT"] and cfg["IOTDA_PROJECT_ID"] and cfg["IOTDA_IAM_TOKEN"]:
        return "iotda"
    if device.transport == "mqtt" and cfg["MQTT_BROKER_URL"]:
        return "mqtt"
    return "http"


def dispatch(cmd, now=None):
    now = now or utcnow()
    cmd.transport = transport_for(cmd.device)
    cmd.status = "sent"
    cmd.sent_at = now
    cmd.expires_at = now + timedelta(seconds=control_config()["ack_timeout_seconds"])
    db.session.commit()
    if cmd.transport == "sim":
        return _finish(cmd, 0, apply_sim_effect(cmd, now), now)
    if cmd.transport == "iotda":
        return _send_iotda(cmd, now)
    if cmd.transport == "mqtt":
        _send_mqtt(cmd)
    return cmd


def _finish(cmd, result_code, paras, now=None):
    cmd.status = "done" if result_code == 0 else "failed"
    cmd.result = {"result_code": result_code, "paras": paras}
    cmd.completed_at = now or utcnow()
    db.session.commit()
    return cmd


def record_response(request_id, body, device=None, now=None):
    """Device acknowledgement (HTTP poll path or MQTT response topic). Returns the command or None."""
    now = now or utcnow()
    cmd = DeviceCommand.query.filter_by(request_id=request_id).first()
    if cmd is None or (device is not None and cmd.device_id != device.id):
        return None
    if cmd.status != "sent":
        return cmd
    if cmd.expires_at and now > cmd.expires_at:
        _expire(cmd, now)
        return cmd
    body = body if isinstance(body, dict) else {}
    code = body.get("result_code", 0)
    if not isinstance(code, int) or isinstance(code, bool):
        code = 1
    paras = body.get("paras") if isinstance(body.get("paras"), dict) else {}
    return _finish(cmd, code, paras, now)


def _expire(cmd, now):
    cmd.status = "expired"
    cmd.completed_at = now
    db.session.commit()


def expire_stale(now=None):
    """Awaiting commands past the confirm window and sent commands past the ack timeout become expired."""
    now = now or utcnow()
    stale = DeviceCommand.query.filter(DeviceCommand.status.in_(OPEN), DeviceCommand.expires_at.isnot(None),
                                       DeviceCommand.expires_at < now).all()
    for cmd in stale:
        cmd.status = "expired"
        cmd.completed_at = now
    if stale:
        db.session.commit()
    return len(stale)


def pending_for_device(device, now=None):
    expire_stale(now)
    rows = DeviceCommand.query.filter_by(device_id=device.id, status="sent").order_by(DeviceCommand.id).all()
    return [{"request_id": c.request_id, **command_payload(c)} for c in rows]


def iotda_device_id(device):
    product = current_app.config["IOTDA_PRODUCT_ID"]
    return f"{product}_{device.uid}" if product else device.uid


def _send_iotda(cmd, now):
    """IoTDA synchronous command API: the platform relays to the device and returns its response."""
    cfg = current_app.config
    url = f"{cfg['IOTDA_API_ENDPOINT'].rstrip('/')}/v5/iot/{cfg['IOTDA_PROJECT_ID']}/devices/{iotda_device_id(cmd.device)}/commands"
    try:
        res = requests.post(url, json=command_payload(cmd), headers={"X-Auth-Token": cfg["IOTDA_IAM_TOKEN"]}, timeout=30)
        body = res.json() if res.content else {}
    except (requests.RequestException, ValueError) as exc:
        return _finish(cmd, 1, {"error": f"IoTDA request failed: {exc.__class__.__name__}"}, utcnow())
    if res.status_code != 200:
        return _finish(cmd, 1, {"error": f"IoTDA HTTP {res.status_code}", "detail": body.get("error_msg")}, utcnow())
    response = body.get("response") or {}
    code = response.get("result_code", 0)
    return _finish(cmd, code if isinstance(code, int) else 1,
                   {**(response.get("paras") or {}), "iotda_command_id": body.get("command_id")}, utcnow())


def command_topic(uid, request_id):
    return f"$oc/devices/{uid}/sys/commands/request_id={request_id}"


def _send_mqtt(cmd):
    from paho.mqtt import publish

    from .mqtt_bridge import parse_broker_url

    cfg = current_app.config
    host, port, tls = parse_broker_url(cfg["MQTT_BROKER_URL"])
    auth = {"username": cfg["MQTT_USERNAME"], "password": cfg["MQTT_PASSWORD"] or None} if cfg["MQTT_USERNAME"] else None
    try:
        publish.single(command_topic(cmd.device.uid, cmd.request_id), json.dumps(command_payload(cmd)), qos=1,
                       hostname=host, port=port, auth=auth, tls={} if tls else None)
    except OSError as exc:
        _finish(cmd, 1, {"error": f"MQTT publish failed: {exc.__class__.__name__}"})


def apply_sim_effect(cmd, now):
    """Simulated valve/doser: push water or nutrients into the plot's simulated sensor state and record a reading."""
    from .device_sim import simulate_device

    cfg = control_config()
    sensor = (Device.query.filter_by(plot_id=cmd.plot_id, kind=SENSOR_KIND, is_simulated=True)
              .order_by(Device.id).first())
    area = plot_area(cmd.plot, cfg)
    result = {"simulated": True}
    if sensor is None:
        return {**result, "note": "no simulated sensor on this plot"}
    simulate_device(sensor, now=now)
    sim = iot_config()["simulator"]
    state = dict(sensor.sim_state or {})
    last = (SensorReading.query.filter_by(device_id=sensor.id).order_by(SensorReading.ts.desc()).first())
    if not state or last is None:
        return {**result, "note": "simulated sensor has no state yet"}
    if cmd.action == "water":
        mm = cmd.amount / area
        before = state["soil_moisture_pct"]
        state["soil_moisture_pct"] = min(sim["saturation_pct"], before + mm * 100 / sim["root_zone_mm"])
        result.update(mm=round(mm, 2), moisture_before=round(before, 1), moisture_after=round(state["soil_moisture_pct"], 1))
    else:
        before = state["soil_ec_ds_m"]
        state["soil_ec_ds_m"] = before + cmd.amount / area * cfg["sim"]["ec_per_g_per_m2"]
        result.update(ec_before=round(before, 2), ec_after=round(state["soil_ec_ds_m"], 2))
    sensor.sim_state = state
    reading = {m: getattr(last, m) for m in SensorReading.METRICS if getattr(last, m) is not None}
    reading.update(soil_moisture_pct=round(state["soil_moisture_pct"], 1), soil_ec_ds_m=round(state["soil_ec_ds_m"], 2),
                   ts=max(now, last.ts + timedelta(seconds=1)).isoformat() + "+00:00")
    ingest(sensor, [reading], now=max(now, last.ts + timedelta(seconds=1)), transport="sim")
    return result


def parse_schedule(data):
    action = data.get("action")
    if action not in ACTIONS:
        raise ControlError(f"action must be one of {', '.join(ACTIONS)}")
    amount = data.get("amount")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        raise ControlError("amount must be a positive number")
    t = data.get("time_local", "")
    try:
        datetime.strptime(t, "%H:%M")
    except (TypeError, ValueError):
        raise ControlError("time_local must be HH:MM") from None
    days = data.get("days", "0123456")
    if not isinstance(days, str) or not days or any(c not in "0123456" for c in days):
        raise ControlError("days must be weekday digits 0 (Mon) – 6 (Sun)")
    return {"action": action, "amount": float(amount), "time_local": t, "days": "".join(sorted(set(days)))}


def create_schedule(plot, data, user=None):
    fields = parse_schedule(data)
    pick_actuator(plot, fields["action"], data.get("device_id"))
    if fields["amount"] > limits(plot)[fields["action"]]["max_command"]:
        raise ControlError("amount is above the per-command limit")
    sched = ControlSchedule(plot_id=plot.id, device_id=data.get("device_id"), created_by=user.id if user else None,
                            **fields)
    db.session.add(sched)
    db.session.commit()
    return sched


def run_due_schedules(now=None):
    """Run every enabled schedule whose local time has passed today and has not run today. Returns commands."""
    now = now or utcnow()
    expire_stale(now)
    local = local_now(now)
    today: date = local.date()
    out = []
    for sched in ControlSchedule.query.filter_by(enabled=True).all():
        if str(local.weekday()) not in sched.days or sched.last_run_date == today:
            continue
        if local.strftime("%H:%M") < sched.time_local:
            continue
        sched.last_run_date = today
        db.session.commit()
        try:
            out.append(request_command(sched.plot, sched.action, sched.amount, device_id=sched.device_id,
                                       source="schedule", schedule=sched, now=now))
        except ControlError:
            log.warning("schedule %s could not run: no actuator", sched.id)
    return out


def control_state(plot, now=None, limit=50):
    now = now or utcnow()
    expire_stale(now)
    commands = (DeviceCommand.query.filter_by(plot_id=plot.id).order_by(DeviceCommand.id.desc()).limit(limit).all())
    schedules = ControlSchedule.query.filter_by(plot_id=plot.id).order_by(ControlSchedule.time_local).all()
    acts = actuators(plot)
    return {
        "plot_id": plot.id,
        "actuators": [{**d.to_dict(), "action": ACTUATOR_KINDS[d.kind], "online": _device_online(d, now)} for d in acts],
        "commands": [c.to_dict() for c in commands],
        "schedules": [s.to_dict() for s in schedules],
        "limits": limits(plot),
        "simulated": any(d.is_simulated for d in acts),
        "local_time": local_now(now).strftime("%H:%M"),
    }
