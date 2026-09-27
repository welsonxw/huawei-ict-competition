from flask import Blueprint, jsonify, request

from ..models import Device
from ..services.auth import can_access_plot, current_user, login_required
from ..services.device_sim import simulate_device
from ..services.iot import IoTError, authenticate_device, create_device, get_plot, ingest, monitor
from ..services.iotda import check_push_token, handle_push

bp = Blueprint("iot", __name__)


@bp.post("/iot/readings")
def post_readings():
    """Device ingest. Headers X-Device-Id / X-Device-Key; body = one reading or {"readings": [...]}."""
    device = authenticate_device(request.headers.get("X-Device-Id"), request.headers.get("X-Device-Key"))
    if device is None:
        return jsonify(error="unknown device or bad key"), 401
    data = request.get_json(silent=True)
    payloads = data.get("readings", data) if isinstance(data, dict) else data
    try:
        rows = ingest(device, payloads)
    except IoTError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(accepted=len(rows), device=device.uid, is_simulated=device.is_simulated), 201


@bp.post("/iot/iotda/push/<token>")
def iotda_push(token):
    """Huawei Cloud IoTDA data forwarding (HTTP push) target. The secret token is part of the rule's URL."""
    if not check_push_token(token):
        return jsonify(error="not found"), 404
    try:
        device, rows = handle_push(request.get_json(silent=True))
    except LookupError:
        # 200 so IoTDA does not blocklist the endpoint over a device we have not registered.
        return jsonify(accepted=0, error="unknown device"), 200
    except IoTError as exc:
        return jsonify(accepted=0, error=str(exc)), 200
    return jsonify(accepted=len(rows), device=device.uid), 200


@bp.get("/plots/<int:plot_id>/devices")
@login_required()
def list_devices(plot_id):
    plot = get_plot(plot_id)
    if not can_access_plot(current_user(), plot):
        return jsonify(error="plot not found"), 404
    return jsonify([d.to_dict() for d in Device.query.filter_by(plot_id=plot.id).order_by(Device.id)])


@bp.post("/plots/<int:plot_id>/devices")
@login_required()
def add_device(plot_id):
    plot = get_plot(plot_id)
    if not can_access_plot(current_user(), plot):
        return jsonify(error="plot not found"), 404
    data = request.get_json(silent=True) or {}
    simulated = data.get("simulated") is True
    kind = data.get("kind", "sensor")
    try:
        device, key = create_device(plot, data.get("name"), simulated=simulated, kind=kind)
    except IoTError as exc:
        return jsonify(error=str(exc)), 400
    body = {**device.to_dict(), "key": None if simulated else key}
    if simulated and kind == "sensor":
        body["readings_added"] = simulate_device(device)
    return jsonify(body), 201


@bp.get("/plots/<int:plot_id>/monitor")
@login_required()
def plot_monitor(plot_id):
    plot = get_plot(plot_id)
    if not can_access_plot(current_user(), plot):
        return jsonify(error="plot not found"), 404
    try:
        hours = int(request.args.get("hours", 24))
    except ValueError:
        return jsonify(error="hours must be an integer"), 400
    return jsonify(monitor(plot, hours))
