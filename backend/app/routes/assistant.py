from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import Scan
from ..services.assistant import answer
from ..services.auth import login_required
from ..services.config_loader import thresholds
from ..services.scans import plan_for

bp = Blueprint("assistant", __name__)


@bp.post("/assistant")
@login_required()
def ask():
    data = request.get_json(silent=True) or {}
    lang = data.get("lang", "en")
    if lang not in ("en", "ms"):
        return jsonify(error="lang must be en or ms"), 400
    try:
        scan = db.session.get(Scan, int(data.get("scan_id")))
    except (TypeError, ValueError):
        return jsonify(error="scan_id is required"), 400
    if scan is None:
        return jsonify(error="scan not found"), 404
    question = str(data.get("question", "")).strip()[:500]
    low_conf = scan.review_status == "pending" or (
        not scan.confirmed_label and (scan.is_stub or scan.confidence < thresholds()["scan"]["low_confidence"]))
    return jsonify(answer(scan, plan_for(scan, low_conf), question, lang, low_conf))
