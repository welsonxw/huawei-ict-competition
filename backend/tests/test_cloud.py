import base64
import io

from PIL import Image

from app.services.storage import OBSStorage, obs_region
from ml.serve import create_app as create_infer_app


def test_obs_region_and_virtual_hosted_client():
    assert obs_region("https://obs.ap-southeast-3.myhuaweicloud.com") == "ap-southeast-3"
    assert obs_region("https://obs.my-kualalumpur-1.myhuaweicloud.com/") == "my-kualalumpur-1"
    s = OBSStorage("https://obs.ap-southeast-3.myhuaweicloud.com", "taniguard", "ak", "sk")
    assert s.client.meta.region_name == "ap-southeast-3"
    assert s.client.meta.config.s3["addressing_style"] == "virtual"


def test_system_reports_backends_without_secrets(app, client):
    app.config.update(STORAGE_BACKEND="obs", PREDICTOR="remote", LLM_ENDPOINT="https://x", LLM_API_KEY="secret")
    body = client.get("/api/system").get_json()
    assert body == {"database": "sqlite", "cache": "fakeredis", "storage": "obs", "predictor": "modelarts",
                    "assistant": "llm", "scheduler": False}


class FakePredictor:
    def __init__(self, stub=False):
        self.stub = stub

    def predict(self, image, crop):
        if self.stub:
            return {"is_stub": True, "stub_reason": "no weights"}
        return {"label": "early_blight", "confidence": 0.9, "top3": [{"label": "early_blight", "confidence": 0.9}],
                "heatmap": b"png", "severity": 0.2, "model_version": "tomato-resnet9-v1", "is_stub": False}


def _jpeg_b64():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (0, 128, 0)).save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


def test_modelarts_server_contract():
    c = create_infer_app(FakePredictor()).test_client()
    assert c.get("/health").get_json() == {"status": "OK"}
    body = c.post("/", json={"crop": "tomato", "image": _jpeg_b64()}).get_json()
    assert body["label"] == "early_blight" and base64.b64decode(body["heatmap"]) == b"png"
    assert c.post("/", json={"crop": "rice", "image": _jpeg_b64()}).status_code == 400
    assert c.post("/", json={"crop": "tomato", "image": "not-base64!"}).status_code == 400
    stub = create_infer_app(FakePredictor(stub=True)).test_client()
    assert stub.post("/", json={"crop": "tomato", "image": _jpeg_b64()}).status_code == 503
