import math

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Plot, Scan
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
def recommend_route():
    data = request.get_json(silent=True) or {}
    try:
        crop = data.get("crop")
        area = _num(data.get("area_m2"), "area_m2")
        plants = _num(data.get("num_plants"), "num_plants")
        deficiency = False
        if data.get("plot_id"):
            plot = db.session.get(Plot, int(data["plot_id"]))
            if plot is None:
                return jsonify(error="plot not found"), 404
            crop = plot.crop
            area = area or plot.area_m2
            plants = plants or plot.num_plants
            latest = Scan.query.filter_by(plot_id=plot.id).order_by(Scan.created_at.desc()).first()
            deficiency = bool(latest and latest.diagnosis == "nutrient_deficiency")
        ph = _num(data.get("ph"), "ph")
        if ph is not None and not 0 <= ph <= 14:
            raise FertiliserError("ph must be between 0 and 14")
        previous = str(data.get("previous_fertiliser") or "").strip()[:120] or None
        out = recommend(
            crop, data.get("stage"), area, int(plants) if plants else None, ph=ph,
            soil=data.get("soil"), previous=previous, deficiency_hint=deficiency,
        )
    except FertiliserError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(out)
