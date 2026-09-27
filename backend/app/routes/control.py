from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import ControlSchedule, DeviceCommand
from ..models.core import utcnow
from ..services.auth import can_access_plot, current_user, login_required
from ..services.control import (
    ControlError,
    cancel_command,
    confirm_command,
    control_state,
    create_schedule,
    pending_for_device,
    record_response,
    request_command,
)
from ..services.iot import authenticate_device, get_plot

bp = Blueprint("control", __name__)


def can_control(user, plot):
    """Only the farmer who owns a plot may actuate its devices; experts can view the log."""
    return user is not None and plot is not None and user.role == "farmer" and plot.owner_id == user.id


def _plot_or_404(plot_id):
    plot = get_plot(plot_id)
    return plot if can_access_plot(current_user(), plot) else None


def _owned(plot):
    if plot is None:
        return jsonify(error="plot not found"), 404
    if not can_control(current_user(), plot):
        return jsonify(error="only the plot's farmer can control its devices"), 403
    return None


@bp.get("/plots/<int:plot_id>/control")
@login_required()
def get_control(plot_id):
    plot = _plot_or_404(plot_id)
    if plot is None:
        return jsonify(error="plot not found"), 404
    return jsonify({**control_state(plot), "can_control": can_control(current_user(), plot)})


@bp.post("/plots/<int:plot_id>/commands")
@login_required()
def post_command(plot_id):
    plot = _plot_or_404(plot_id)
    if (err := _owned(plot)) is not None:
        return err
    data = request.get_json(silent=True) or {}
    source = data.get("source", "manual")
    if source not in ("manual", "game", "optimizer"):
        return jsonify(error="source must be manual, game or optimizer"), 400
    try:
        cmd = request_command(plot, data.get("action"), data.get("amount"), user=current_user(),
                              device_id=data.get("device_id"), source=source)
    except ControlError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(cmd.to_dict()), 201


def _command_or_error(command_id):
    cmd = db.session.get(DeviceCommand, command_id)
    plot = cmd.plot if cmd else None
    if plot is None or not can_access_plot(current_user(), plot):
        return None, (jsonify(error="command not found"), 404)
    if (err := _owned(plot)) is not None:
        return None, err
    return cmd, None


@bp.post("/commands/<int:command_id>/confirm")
@login_required()
def post_confirm(command_id):
    cmd, err = _command_or_error(command_id)
    if err:
        return err
    try:
        cmd = confirm_command(cmd)
    except ControlError as exc:
        return jsonify(error=str(exc), command=cmd.to_dict()), 409
    return jsonify(cmd.to_dict())


@bp.post("/commands/<int:command_id>/cancel")
@login_required()
def post_cancel(command_id):
    cmd, err = _command_or_error(command_id)
    if err:
        return err
    try:
        cmd = cancel_command(cmd)
    except ControlError as exc:
        return jsonify(error=str(exc), command=cmd.to_dict()), 409
    return jsonify(cmd.to_dict())


@bp.post("/plots/<int:plot_id>/schedules")
@login_required()
def post_schedule(plot_id):
    plot = _plot_or_404(plot_id)
    if (err := _owned(plot)) is not None:
        return err
    try:
        sched = create_schedule(plot, request.get_json(silent=True) or {}, user=current_user())
    except ControlError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(sched.to_dict()), 201


def _schedule_or_error(schedule_id):
    sched = db.session.get(ControlSchedule, schedule_id)
    plot = sched.plot if sched else None
    if plot is None or not can_access_plot(current_user(), plot):
        return None, (jsonify(error="schedule not found"), 404)
    if (err := _owned(plot)) is not None:
        return None, err
    return sched, None


@bp.patch("/schedules/<int:schedule_id>")
@login_required()
def patch_schedule(schedule_id):
    sched, err = _schedule_or_error(schedule_id)
    if err:
        return err
    enabled = (request.get_json(silent=True) or {}).get("enabled")
    if not isinstance(enabled, bool):
        return jsonify(error="enabled must be true or false"), 400
    sched.enabled = enabled
    db.session.commit()
    return jsonify(sched.to_dict())


@bp.delete("/schedules/<int:schedule_id>")
@login_required()
def delete_schedule(schedule_id):
    sched, err = _schedule_or_error(schedule_id)
    if err:
        return err
    db.session.delete(sched)
    db.session.commit()
    return jsonify(deleted=schedule_id)


def _device():
    return authenticate_device(request.headers.get("X-Device-Id"), request.headers.get("X-Device-Key"))


@bp.get("/iot/commands")
def device_poll():
    """HTTP actuator path: the device polls for sent commands (IoTDA command format plus request_id)."""
    device = _device()
    if device is None:
        return jsonify(error="unknown device or bad key"), 401
    device.last_seen_at = utcnow()
    device.transport = device.transport or "http"
    db.session.commit()
    return jsonify(commands=pending_for_device(device))


@bp.post("/iot/commands/<request_id>/response")
def device_response(request_id):
    device = _device()
    if device is None:
        return jsonify(error="unknown device or bad key"), 401
    cmd = record_response(request_id, request.get_json(silent=True), device=device)
    if cmd is None:
        return jsonify(error="command not found"), 404
    return jsonify(cmd.to_dict())
