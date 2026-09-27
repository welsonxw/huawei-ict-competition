"""Which backing service each layer is using, for the "Behind the scenes" tab. No hosts or keys are exposed."""
from flask import Blueprint, current_app, jsonify

from ..extensions import db

bp = Blueprint("system", __name__)


@bp.get("/system")
def system():
    cfg = current_app.config
    redis_url = cfg["REDIS_URL"]
    return jsonify({
        "database": db.engine.dialect.name,
        "cache": "fakeredis" if redis_url.startswith("fakeredis") else "redis",
        "storage": "obs" if cfg["STORAGE_BACKEND"] == "obs" else "local",
        "predictor": "modelarts" if cfg["PREDICTOR"] == "remote" else "local",
        "assistant": "llm" if cfg["LLM_ENDPOINT"] and cfg["LLM_API_KEY"] else "template",
        "iot": "iotda" if cfg["IOTDA_PUSH_TOKEN"] else ("mqtt" if cfg["MQTT_BROKER_URL"] else "http"),
        "scheduler": bool(cfg["ENABLE_SCHEDULER"]),
    })
