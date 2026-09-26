from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from ..extensions import db
from ..models import Scan
from ..services.auth import current_user, login_required
from ..services.review import LABELS, ReviewError, label_options, model_metrics, review, training_set_zip

bp = Blueprint("review", __name__)


@bp.get("/review/queue")
@login_required("expert")
def review_queue():
    rows = (Scan.query.filter_by(review_status="pending", is_simulated=False)
            .order_by(Scan.created_at.desc()).limit(100).all())
    return jsonify([s.to_dict() for s in rows])


@bp.get("/review/labels")
def labels():
    crop = request.args.get("crop", "")
    if crop not in LABELS:
        return jsonify(error="crop must be chilli or tomato"), 400
    return jsonify(label_options(crop))


@bp.post("/review/<int:scan_id>")
@login_required("expert")
def review_scan(scan_id):
    scan = db.session.get(Scan, scan_id)
    if scan is None:
        return jsonify(error="scan not found"), 404
    data = request.get_json(silent=True) or {}
    try:
        scan = review(scan, str(data.get("label", "")), current_user().username)
    except ReviewError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(scan.to_dict())


@bp.get("/export/training-set")
@login_required("expert")
def export_training_set():
    crop = request.args.get("crop") or None
    if crop and crop not in LABELS:
        return jsonify(error="crop must be chilli or tomato"), 400
    buf, _ = training_set_zip(crop)
    name = f"training-set-{crop or 'all'}-{datetime.now():%Y%m%d}.zip"
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=name)


@bp.get("/model/metrics")
def metrics():
    return jsonify(model_metrics())
