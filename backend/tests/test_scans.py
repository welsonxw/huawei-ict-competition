import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.services import predictor as predictor_mod
from app.services.scans import create_plot

ROOT = Path(__file__).resolve().parents[2]
HAS_WEIGHTS = (ROOT / "ml" / "weights" / predictor_mod.TOMATO_WEIGHTS).exists()


@pytest.fixture(autouse=True)
def no_network(monkeypatch, tmp_path, app):
    monkeypatch.setattr("app.services.scans.get_forecast", lambda lat, lon: None)
    app.config["LOCAL_STORAGE_DIR"] = tmp_path
    app.extensions.pop("storage", None)


def _png(color=(40, 160, 60)):
    buf = io.BytesIO()
    arr = np.zeros((128, 128, 3), dtype=np.uint8) + np.array(color, dtype=np.uint8)
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


class FixedPredictor(predictor_mod.Predictor):
    def __init__(self, confidence):
        self.confidence = confidence

    def predict(self, image, crop):
        return {
            "label": "early_blight", "confidence": self.confidence,
            "top3": [{"label": "early_blight", "confidence": self.confidence}],
            "heatmap": _png((255, 0, 0)), "severity": 0.2, "model_version": "test", "is_stub": False,
        }


def _upload(client, plot_id, crop="tomato"):
    return client.post(
        "/api/scans",
        data={"crop": crop, "plot_id": str(plot_id), "image": (io.BytesIO(_png()), "leaf.png")},
        content_type="multipart/form-data",
    )


def test_scan_saves_and_returns_plan(app, client):
    app.extensions["predictor"] = FixedPredictor(0.9)
    plot = create_plot("Plot C", "tomato", 1.85, 103.33)
    res = _upload(client, plot.id)
    assert res.status_code == 201
    body = res.get_json()
    assert body["scan"]["diagnosis"] == "early_blight"
    assert body["scan"]["region"] == "JHR"
    assert body["low_confidence"] is False
    assert 3 <= len(body["action_plan"]["en"]) <= 5 and len(body["action_plan"]["ms"]) == len(body["action_plan"]["en"])
    assert client.get(body["scan"]["heatmap_url"]).mimetype == "image/png"
    assert client.get("/api/review/queue").get_json() == []


def test_low_confidence_goes_to_review_queue(app, client):
    app.extensions["predictor"] = FixedPredictor(0.4)
    plot = create_plot("Plot C", "tomato", 1.85, 103.33)
    body = _upload(client, plot.id).get_json()
    assert body["low_confidence"] is True
    assert body["action_plan"]["en"][0].startswith("Not sure")
    queue = client.get("/api/review/queue").get_json()
    assert [s["id"] for s in queue] == [body["scan"]["id"]]


def test_rejects_non_image(app, client):
    plot = create_plot("Plot C", "tomato", 1.85, 103.33)
    res = client.post("/api/scans", data={"crop": "tomato", "plot_id": str(plot.id), "image": (io.BytesIO(b"nope"), "x.png")},
                      content_type="multipart/form-data")
    assert res.status_code == 400


def test_stub_when_weights_missing(tmp_path):
    p = predictor_mod.LocalTorchPredictor(tmp_path)
    out = p.predict(Image.new("RGB", (300, 300), (30, 120, 30)), "chilli")
    assert out["is_stub"] is True and out["label"] in predictor_mod.CROP_LABELS["chilli"]
    assert len(out["top3"]) == 3 and out["heatmap"][:4] == b"\x89PNG"


@pytest.mark.skipif(not HAS_WEIGHTS, reason="tomato weights not downloaded (scripts/download_model.py)")
def test_real_tomato_model_on_agritech_sample():
    sample = ROOT / "ml" / "samples" / "TomatoEarlyBlight1.JPG"
    p = predictor_mod.LocalTorchPredictor(ROOT / "ml" / "weights")
    out = p.predict(Image.open(sample), "tomato")
    assert out["is_stub"] is False
    assert out["label"] == "early_blight" and out["confidence"] > 0.6
    assert 0 <= out["severity"] <= 1


def test_stub_prediction_always_goes_to_review(app, client, tmp_path):
    app.extensions["predictor"] = predictor_mod.LocalTorchPredictor(tmp_path)
    plot = create_plot("Plot A", "chilli", 1.85, 103.33)
    body = _upload(client, plot.id, crop="chilli").get_json()
    assert body["scan"]["is_stub"] is True and body["low_confidence"] is True
    assert body["scan"]["review_status"] == "pending"


def test_crop_must_match_plot(app, client):
    app.extensions["predictor"] = FixedPredictor(0.9)
    plot = create_plot("Plot A", "chilli", 1.85, 103.33)
    assert _upload(client, plot.id, crop="tomato").status_code == 400


def test_forecast_failure_still_returns_scan(app, client, monkeypatch):
    app.extensions["predictor"] = FixedPredictor(0.9)

    def boom(lat, lon):
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.services.scans.get_forecast", boom)
    plot = create_plot("Plot C", "tomato", 1.85, 103.33)
    res = _upload(client, plot.id)
    assert res.status_code == 201
    assert res.get_json()["action_plan"]["weather"] is None


def test_plot_rejects_invalid_coordinates(client):
    for lat, lon in (("nan", 103), (91, 103), (1.8, "inf")):
        res = client.post("/api/plots", json={"name": "X", "crop": "tomato", "lat": lat, "lon": lon})
        assert res.status_code == 400


def test_missing_weights_are_picked_up_later(tmp_path, monkeypatch):
    p = predictor_mod.LocalTorchPredictor(tmp_path)
    assert p._load("chilli") is None
    assert "chilli" not in p._models
