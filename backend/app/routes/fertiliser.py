import math

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Plot, Scan
from ..services.auth import login_required
from ..services.fertiliser import STAGES, FertiliserError, load_products, recommend, stage_requirements

bp = Blueprint("fertiliser", __name__)


@bp.get("/fertiliser/products")
def products():
    return jsonify(load_products())


@bp.get("/fertiliser/requirements")
def requirements():
    crop = request.args.get("crop", "chilli")
    if crop not in ("chilli", "tomato"):
        return jsonify(error="crop must be chilli or tomato"), 400
    return jsonify({"crop": crop, "stages": STAGES, "requirements": stage_requirements(crop)})


def _num(value, name):
    if value in (None, ""):
        return None
    try:
        x = float(value)
    except (TypeError, ValueError) as exc:
        raise FertiliserError(f"{name} must be a number") from exc
    if not math.isfinite(x):
        raise FertiliserError(f"{name} must be a number")
    return x


@bp.post("/fertiliser/recommend")
@login_required()
def recommend_route():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify(error="request body must be a JSON object"), 400
    try:
        crop = data.get("crop")
        area = _num(data.get("area_m2"), "area_m2")
        plants = _num(data.get("num_plants"), "num_plants")
        deficiency = False
        if data.get("plot_id"):
            plot_id = _num(data["plot_id"], "plot_id")
            if plot_id is None or not plot_id.is_integer():
                raise FertiliserError("plot_id must be an integer")
            plot = db.session.get(Plot, int(plot_id))
            if plot is None:
                return jsonify(error="plot not found"), 404
            crop = plot.crop
            area = area or plot.area_m2
            plants = plants or plot.num_plants
            latest = Scan.query.filter_by(plot_id=plot.id).order_by(Scan.created_at.desc()).first()
            deficiency = bool(latest and latest.diagnosis == "nutrient_deficiency")
        if plants is not None and (plants < 1 or not float(plants).is_integer()):
            raise FertiliserError("num_plants must be a positive whole number")
        soil = data.get("soil")
        if soil is not None and not isinstance(soil, dict):
            raise FertiliserError("soil must be an object like {\"n\": \"low\"}")
        ph = _num(data.get("ph"), "ph")
        if ph is not None and not 0 <= ph <= 14:
            raise FertiliserError("ph must be between 0 and 14")
        previous = str(data.get("previous_fertiliser") or "").strip()[:120] or None
        out = recommend(
            crop, data.get("stage"), area, int(plants) if plants else None, ph=ph,
            soil=soil, previous=previous, deficiency_hint=deficiency,
        )
    except FertiliserError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(out)
