from datetime import timedelta

from app.models import Scan
from app.services.weather import now_local


def series_from_now(rain):
    start = now_local().replace(minute=0, second=0, microsecond=0) - timedelta(days=1)
    times = [(start + timedelta(hours=i)).isoformat(timespec="minutes") for i in range(96)]
    return {"time": times, "temp": [25.0] * 96, "rh": [90.0] * 96, "rain": [rain] * 96}


def test_game_outlook_demo_uses_risk_engine(app, client):
    from app.services.demo import seed_demo
    from app.services.profiles import seed_profiles

    seed_profiles()
    seed_demo()
    before = Scan.query.count()
    body = client.get("/api/game/outlook?lat=1.99&lon=103.32&scenario=demo").get_json()
    assert body["simulated"] is True and body["label"] == "Simulated scenario"
    anth = next(d for d in body["diseases"] if d["disease"] == "anthracnose")
    assert set(anth["bands"]) == {"0", "3", "5"}
    assert anth["bands"]["5"] in ("medium", "high") and anth["reports"] > 0
    assert anth["plan"]["en"] and anth["plan"]["ms"] and "ladang anda" in " ".join(anth["plan"]["ms"])
    assert body["weather"]["hours"] == 48
    assert Scan.query.count() == before  # read-only


def test_game_outlook_live_far_from_reports_is_low(app, client, monkeypatch):
    from app.services import weather
    from app.services.profiles import seed_profiles

    seed_profiles()
    monkeypatch.setattr(weather, "fetch_open_meteo_many", lambda coords, *a, **k: [series_from_now(2.0) for _ in coords])
    body = client.get("/api/game/outlook?lat=5.5&lon=116.0").get_json()
    assert body["simulated"] is False and body["label"] is None
    assert all(b == "low" for d in body["diseases"] for b in d["bands"].values())
    assert body["weather"]["rain_hours"] > 0


def test_game_outlook_validation(client):
    assert client.get("/api/game/outlook").status_code == 400
    assert client.get("/api/game/outlook?lat=51.5&lon=0").status_code == 400
    assert client.get("/api/game/outlook?lat=2&lon=103&scenario=x").status_code == 400
