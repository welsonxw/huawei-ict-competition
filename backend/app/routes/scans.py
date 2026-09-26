import math

from flask import Blueprint, Response, abort, jsonify, request

from ..extensions import db
from ..models import Plot, Scan
from ..services.scans import CROPS, ScanError, create_plot, run_scan
from ..services.storage import get_storage

bp = Blueprint("scans", __name__)


@bp.get("/plots")
def list_plots():
    q = Plot.query
    if request.args.get("include_simulated") != "true":
        q = q.filter_by(is_simulated=False)
    return jsonify([p.to_dict() for p in q.order_by(Plot.id).all()])


@bp.post("/plots")
def add_plot():
    data = request.get_json(silent=True) or {}
    try:
        name = str(data["name"]).strip()[:80]
        crop = data["crop"]
        lat, lon = float(data["lat"]), float(data["lon"])
    except (KeyError, TypeError, ValueError):
        return jsonify(error="name, crop, lat and lon are required"), 400
    if crop not in CROPS or not name:
        return jsonify(error="crop must be chilli or tomato"), 400
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify(error="lat/lon out of range"), 400
    plot = create_plot(name, crop, lat, lon, data.get("area_m2"), data.get("num_plants"))
    return jsonify(plot.to_dict()), 201


@bp.post("/scans")
def create_scan():
    file = request.files.get("image")
    if not file:
        return jsonify(error="image file is required"), 400
    crop = request.form.get("crop", "")
    plot = None
    if request.form.get("plot_id"):
        plot = db.session.get(Plot, int(request.form["plot_id"]))
        if plot is None:
            return jsonify(error="plot not found"), 404
    lat = request.form.get("lat", type=float)
    lon = request.form.get("lon", type=float)
    if lat is not None and lon is not None and not (
        math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
    ):
        return jsonify(error="lat/lon out of range"), 400
    try:
        _, payload = run_scan(file.read(), crop, plot, lat, lon)
    except ScanError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(payload), 201


@bp.get("/scans")
def list_scans():
    q = Scan.query
    if request.args.get("plot_id"):
        q = q.filter_by(plot_id=int(request.args["plot_id"]))
    limit = min(int(request.args.get("limit", 20)), 200)
    return jsonify([s.to_dict() for s in q.order_by(Scan.created_at.desc()).limit(limit).all()])


def _file(scan_id, attr, mimetype):
    scan = db.session.get(Scan, scan_id) or abort(404)
    key = getattr(scan, attr) or abort(404)
    return Response(get_storage().read(key), mimetype=mimetype, headers={"Cache-Control": "max-age=86400"})


@bp.get("/scans/<int:scan_id>/image")
def scan_image(scan_id):
    return _file(scan_id, "image_path", "image/jpeg")


@bp.get("/scans/<int:scan_id>/heatmap")
def scan_heatmap(scan_id):
    return _file(scan_id, "heatmap_path", "image/png")


@bp.get("/review/queue")
def review_queue():
    rows = Scan.query.filter_by(review_status="pending").order_by(Scan.created_at.desc()).limit(100).all()
    return jsonify([s.to_dict() for s in rows])
