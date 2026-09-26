from flask import Blueprint, jsonify, request

from ..services.config_loader import state_boundaries
from ..services.national import get_national

bp = Blueprint("national", __name__)


@bp.get("/national")
def national():
    try:
        return jsonify(get_national(request.args.get("scenario", "live")))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@bp.get("/regions/geojson")
def regions_geojson():
    res = jsonify(state_boundaries())
    res.cache_control.max_age = 86400
    return res
