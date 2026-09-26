from flask import Blueprint, jsonify, request

from ..services.config_loader import thresholds
from ..services.demo import demo_count
from ..services.profiles import get_profile
from ..services.risk_engine import get_risk, spreading_diseases

bp = Blueprint("risk", __name__)


@bp.get("/risk/diseases")
def diseases():
    items = []
    for crop, disease in spreading_diseases():
        p = get_profile(crop, disease)
        items.append({"crop": crop, "disease": disease, "name": p["name"], "weather_model": p["weather_model"]})
    n = demo_count()
    return jsonify({
        "diseases": items, "horizons": thresholds()["risk"]["horizons_days"],
        "demo_scans": n, "demo_label": "Simulated scenario" if n else None,
    })


@bp.get("/risk")
def risk():
    crop = request.args.get("crop", "chilli")
    disease = request.args.get("disease", "anthracnose")
    scenario = request.args.get("scenario", "live")
    try:
        horizon = int(request.args.get("horizon", 0))
    except ValueError:
        return jsonify(error="horizon must be an integer"), 400
    if (crop, disease) not in spreading_diseases():
        return jsonify(error="unknown crop/disease for the risk map"), 400
    try:
        return jsonify(get_risk(crop, disease, horizon, scenario))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
