import math

from flask import Blueprint, jsonify, request

from ..services.auth import can_access_plot, current_user, login_required
from ..services.game import outlook
from ..services.iot import get_plot
from ..services.myfarm import farm_view
from ..services.risk_engine import SCENARIOS
from .control import can_control

bp = Blueprint("game", __name__)


@bp.get("/game/outlook")
def game_outlook():
    try:
        lat, lon = float(request.args["lat"]), float(request.args["lon"])
    except (KeyError, ValueError):
        return jsonify(error="lat and lon are required"), 400
    if not (math.isfinite(lat) and math.isfinite(lon) and 0 <= lat <= 8 and 99 <= lon <= 120):
        return jsonify(error="lat/lon must be inside Malaysia"), 400
    scenario = request.args.get("scenario", "live")
    if scenario not in SCENARIOS:
        return jsonify(error="scenario must be live or demo"), 400
    return jsonify(outlook(round(lat, 4), round(lon, 4), scenario))


@bp.get("/plots/<int:plot_id>/farm")
@login_required()
def my_farm(plot_id):
    plot = get_plot(plot_id)
    user = current_user()
    if not can_access_plot(user, plot):
        return jsonify(error="plot not found"), 404
    view = farm_view(plot)
    view["control"]["can_control"] = can_control(user, plot)
    return jsonify(view)
