from flask import Blueprint, jsonify
from sqlalchemy import text

from ..extensions import cache, db

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    status = {"database": "ok", "redis": "ok"}
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:
        status["database"] = f"error: {exc.__class__.__name__}"
    try:
        cache.client.ping()
    except Exception as exc:
        status["redis"] = f"error: {exc.__class__.__name__}"
    healthy = all(v == "ok" for v in status.values())
    return jsonify({"status": "ok" if healthy else "degraded", **status}), 200 if healthy else 503
