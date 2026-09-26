"""Standalone inference server for a Huawei Cloud ModelArts real-time service (custom image).

Speaks the contract RemoteEndpointPredictor expects:
    POST /   {"crop": "tomato"|"chilli", "image": <base64 JPEG>}
          -> {"label", "confidence", "top3", "heatmap": <base64 PNG>, "severity", "model_version"}
    GET  /health -> {"status": "OK"}

ModelArts copies the OBS model package to /home/mind/model; set MODEL_DIR to change it.
Run locally: PYTHONPATH=.:backend gunicorn -b 0.0.0.0:8080 ml.serve:app
"""
import base64
import binascii
import io
import os

from flask import Flask, jsonify, request
from PIL import Image, UnidentifiedImageError

from app.services.predictor import CROP_LABELS, LocalTorchPredictor


def create_app(predictor=None):
    app = Flask(__name__)
    model = predictor or LocalTorchPredictor(
        os.getenv("MODEL_DIR", "/home/mind/model"), float(os.getenv("SEVERITY_ACTIVATION", "0.5"))
    )

    @app.get("/health")
    def health():
        return jsonify(status="OK")

    @app.post("/")
    def predict():
        body = request.get_json(silent=True) or {}
        crop = body.get("crop")
        if crop not in CROP_LABELS:
            return jsonify(error="crop must be tomato or chilli"), 400
        try:
            image = Image.open(io.BytesIO(base64.b64decode(body.get("image", ""), validate=True)))
            image.load()
        except (binascii.Error, UnidentifiedImageError, OSError, ValueError):
            return jsonify(error="image must be a base64-encoded JPEG or PNG"), 400
        out = model.predict(image.convert("RGB"), crop)
        if out.get("is_stub"):
            return jsonify(error=out.get("stub_reason", "model not loaded")), 503
        heatmap = out.get("heatmap")
        return jsonify({
            "label": out["label"],
            "confidence": out["confidence"],
            "top3": out["top3"],
            "heatmap": base64.b64encode(heatmap).decode() if heatmap else None,
            "severity": out["severity"],
            "model_version": out["model_version"],
        })

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
