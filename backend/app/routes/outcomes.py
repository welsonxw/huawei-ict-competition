from datetime import date

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import HarvestRecord
from ..services.auth import current_user, login_required
from ..services.learning import learn
from .control import _owned, _plot_or_404, can_control

bp = Blueprint("outcomes", __name__)


@bp.get("/plots/<int:plot_id>/learning")
@login_required()
def get_learning(plot_id):
    plot = _plot_or_404(plot_id)
    if plot is None:
        return jsonify(error="plot not found"), 404
    return jsonify({**learn(plot), "can_control": can_control(current_user(), plot)})


@bp.get("/plots/<int:plot_id>/harvests")
@login_required()
def list_harvests(plot_id):
    plot = _plot_or_404(plot_id)
    if plot is None:
        return jsonify(error="plot not found"), 404
    rows = HarvestRecord.query.filter_by(plot_id=plot.id).order_by(HarvestRecord.harvested_on.desc()).all()
    return jsonify(harvests=[r.to_dict() for r in rows])


@bp.post("/plots/<int:plot_id>/harvests")
@login_required()
def add_harvest(plot_id):
    plot = _plot_or_404(plot_id)
    denied = _owned(plot)
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    kg = data.get("kg")
    if not isinstance(kg, (int, float)) or isinstance(kg, bool) or not 0 < kg < 1_000_000:
        return jsonify(error="kg must be a positive number"), 400
    try:
        day = date.fromisoformat(data.get("harvested_on") or "")
    except (TypeError, ValueError):
        return jsonify(error="harvested_on must be YYYY-MM-DD"), 400
    if day > date.today():
        return jsonify(error="harvested_on cannot be in the future"), 400
    notes = (data.get("notes") or "")[:200] or None
    rec = HarvestRecord(plot_id=plot.id, harvested_on=day, kg=float(kg), notes=notes, created_by=current_user().id)
    db.session.add(rec)
    db.session.commit()
    return jsonify(rec.to_dict()), 201
