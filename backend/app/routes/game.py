import math

from flask import Blueprint, jsonify, request

from ..services.game import outlook
from ..services.risk_engine import SCENARIOS

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
