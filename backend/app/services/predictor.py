"""Disease inference behind one interface.

    predict(image, crop) -> {label, confidence, top3, heatmap, severity, model_version, is_stub}

`LocalTorchPredictor` runs the PyTorch ResNet9 in-process. `RemoteEndpointPredictor`
calls a Huawei Cloud ModelArts real-time service. Select with PREDICTOR=local|remote.
If model weights are missing, a clearly flagged stub prediction is returned instead.
"""
import base64
import hashlib
import io
import logging
from pathlib import Path

import numpy as np
import requests
from flask import current_app
from PIL import Image

from ml.labels import CHILLI_LABELS, PLANTVILLAGE_LABELS, TOMATO_LABEL_MAP

log = logging.getLogger(__name__)

TOMATO_WEIGHTS = "plant-disease-model.pth"
CHILLI_WEIGHTS = "chilli_resnet9.pth"
CROP_LABELS = {"tomato": sorted(set(TOMATO_LABEL_MAP.values())), "chilli": CHILLI_LABELS}


class Predictor:
    def predict(self, image: Image.Image, crop: str) -> dict:
        raise NotImplementedError


def _stub_prediction(image, crop, severity_threshold, reason):
    """Deterministic placeholder so the app works without model weights. Always flagged is_stub."""
    from ml.gradcam import overlay_png, severity_from_cam

    labels = CROP_LABELS[crop]
    digest = hashlib.sha256(image.tobytes()).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    probs = rng.dirichlet(np.ones(len(labels)) * 0.6)
    order = np.argsort(probs)[::-1]
    yy, xx = np.mgrid[0:256, 0:256] / 255.0
    cy, cx = rng.uniform(0.3, 0.7, size=2)
    cam = np.exp(-(((yy - cy) ** 2) + ((xx - cx) ** 2)) / 0.03)
    return {
        "label": labels[order[0]],
        "confidence": float(probs[order[0]]),
        "top3": [{"label": labels[i], "confidence": float(probs[i])} for i in order[:3]],
        "heatmap": overlay_png(image, cam),
        "severity": severity_from_cam(cam, severity_threshold),
        "model_version": "stub",
        "is_stub": True,
        "stub_reason": reason,
    }


class LocalTorchPredictor(Predictor):
    def __init__(self, model_dir: Path, severity_threshold=0.5):
        self.model_dir = Path(model_dir)
        self.severity_threshold = severity_threshold
        self._models = {}

    def _load(self, crop):
        if crop in self._models:
            return self._models[crop]
        import torch

        from ml.models.resnet9 import ResNet9

        entry = None
        if crop == "tomato":
            path = self.model_dir / TOMATO_WEIGHTS
            if path.exists():
                model = ResNet9(3, len(PLANTVILLAGE_LABELS))
                model.load_state_dict(torch.load(path, map_location="cpu"))
                idx = [i for i, name in enumerate(PLANTVILLAGE_LABELS) if name in TOMATO_LABEL_MAP]
                entry = (model.eval(), idx, [TOMATO_LABEL_MAP[PLANTVILLAGE_LABELS[i]] for i in idx], "tomato-resnet9-v1")
        elif crop == "chilli":
            path = self.model_dir / CHILLI_WEIGHTS
            if path.exists():
                ckpt = torch.load(path, map_location="cpu")
                labels = ckpt["labels"]
                model = ResNet9(3, len(labels))
                model.load_state_dict(ckpt["state_dict"])
                entry = (model.eval(), list(range(len(labels))), labels, ckpt.get("version", "chilli-resnet9"))
        self._models[crop] = entry
        return entry

    def predict(self, image, crop):
        import torch

        from ml.gradcam import gradcam, overlay_png, severity_from_cam
        from ml.transforms import inference_transform

        entry = self._load(crop)
        if entry is None:
            return _stub_prediction(image, crop, self.severity_threshold, f"model file for {crop} not found in {self.model_dir}")
        model, idx, labels, version = entry
        x = inference_transform(image.convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            probs_all = torch.softmax(model(x)[0], dim=0)
        # Confidence is the raw softmax over all model classes, so an off-crop image stays low-confidence.
        probs = probs_all[idx].numpy()
        order = np.argsort(probs)[::-1]
        cam = gradcam(model, x, idx[order[0]])
        return {
            "label": labels[order[0]],
            "confidence": float(probs[order[0]]),
            "top3": [{"label": labels[i], "confidence": float(probs[i])} for i in order[:3]],
            "heatmap": overlay_png(image, cam),
            "severity": severity_from_cam(cam, self.severity_threshold),
            "model_version": version,
            "is_stub": False,
        }


class RemoteEndpointPredictor(Predictor):
    """Calls a ModelArts real-time inference endpoint.

    Request:  POST {endpoint} JSON {"crop": ..., "image": <base64 JPEG>}  header X-Auth-Token
    Response: {"label", "confidence", "top3": [{label, confidence}], "heatmap": <base64 PNG>, "severity"}
    """

    def __init__(self, endpoint, token, timeout=30):
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout

    def predict(self, image, crop):
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=90)
        res = requests.post(
            self.endpoint,
            json={"crop": crop, "image": base64.b64encode(buf.getvalue()).decode()},
            headers={"X-Auth-Token": self.token} if self.token else {},
            timeout=self.timeout,
        )
        res.raise_for_status()
        body = res.json()
        return {
            "label": body["label"],
            "confidence": float(body["confidence"]),
            "top3": body.get("top3", []),
            "heatmap": base64.b64decode(body["heatmap"]) if body.get("heatmap") else None,
            "severity": float(body.get("severity", 0.0)),
            "model_version": body.get("model_version", "modelarts"),
            "is_stub": False,
        }


def get_predictor() -> Predictor:
    app = current_app
    if "predictor" not in app.extensions:
        from .config_loader import thresholds

        cfg = app.config
        if cfg["PREDICTOR"] == "remote":
            app.extensions["predictor"] = RemoteEndpointPredictor(cfg["MODELARTS_ENDPOINT"], cfg["MODELARTS_TOKEN"])
        else:
            app.extensions["predictor"] = LocalTorchPredictor(
                cfg["MODEL_DIR"], thresholds()["scan"]["severity_activation"]
            )
    return app.extensions["predictor"]
