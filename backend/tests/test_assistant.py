import pytest

from app.extensions import db
from app.models import Scan
from app.services.assistant import LLMProvider, OpenAICompatibleProvider, get_provider
from app.services.profiles import seed_profiles
from app.services.scans import locate


@pytest.fixture(autouse=True)
def setup(app, expert, monkeypatch):
    monkeypatch.setattr("app.services.scans.get_forecast", lambda lat, lon: None)
    seed_profiles()


def make_scan(confidence=0.9, diagnosis="anthracnose"):
    cell, region = locate(1.85, 103.33)
    s = Scan(crop="chilli", diagnosis=diagnosis, confidence=confidence, top3=[], severity=0.3, lat=1.85, lon=103.33,
             grid_cell=cell, region=region, review_status="none")
    db.session.add(s)
    db.session.commit()
    return s


def ask(client, scan, question="", lang="en"):
    return client.post("/api/assistant", json={"scan_id": scan.id, "question": question, "lang": lang}).get_json()


def test_template_fallback_without_key(app, client):
    assert get_provider() is None
    scan = make_scan()
    en = ask(client, scan)
    assert en["source"] == "template" and "Anthracnose" in en["answer"] and "1." in en["answer"]
    ms = ask(client, scan, "Adakah ia merebak?", "ms")
    assert ms["source"] == "template" and "merebak" in ms["answer"]


def test_low_confidence_template_asks_for_retake(client):
    assert "retake" in ask(client, make_scan(confidence=0.3), "what is it?")["answer"]


class FakeProvider(LLMProvider):
    def __init__(self, fail=False):
        self.fail, self.messages = fail, None

    def chat(self, messages):
        if self.fail:
            raise RuntimeError("down")
        self.messages = messages
        return "LLM says hello"


def test_llm_used_when_configured_and_falls_back_on_error(app, client):
    fake = FakeProvider()
    app.extensions["llm_provider"] = fake
    out = ask(client, make_scan(), "When can I spray?", "ms")
    assert out == {"answer": "LLM says hello", "source": "llm"}
    assert "Bahasa Melayu" in fake.messages[0]["content"] and "When can I spray?" in fake.messages[1]["content"]
    app.extensions["llm_provider"] = FakeProvider(fail=True)
    assert ask(client, make_scan())["source"] == "template"


def test_provider_from_env(app):
    app.config.update(LLM_ENDPOINT="https://llm.example/v1/chat/completions", LLM_API_KEY="k", LLM_MODEL="m")
    assert isinstance(get_provider(), OpenAICompatibleProvider)


def test_validation(client):
    assert client.post("/api/assistant", json={"lang": "en"}).status_code == 400
    assert client.post("/api/assistant", json={"scan_id": 999, "lang": "en"}).status_code == 404
    assert client.post("/api/assistant", json={"scan_id": 1, "lang": "fr"}).status_code == 400
