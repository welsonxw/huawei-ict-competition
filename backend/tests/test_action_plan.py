from datetime import datetime, timedelta

from app.services.action_plan import action_plan

WEATHER_CFG = {"action_plan_hours": 48, "rain_mm_threshold": 0.5, "leaf_wetness_rh": 90}
SPRAY = {"advice_type": "spray_timing"}


def forecast(rain_at=None, rh=70):
    rain = [0.0] * 72
    if rain_at is not None:
        rain[rain_at] = 4.0
    times = [(START + timedelta(hours=i)).isoformat(timespec="minutes") for i in range(72)]
    return {"time": times, "temp": [28.0] * 72, "rh": [rh] * 72, "rain": rain}


# Open-Meteo series start at local midnight; "now" is 08:00 on the first day.
START = datetime(2026, 1, 10, 0, 0)
NOW = datetime(2026, 1, 10, 8, 0)


def plan(*args, **kw):
    return action_plan(*args, now=NOW, **kw)


def test_plan_changes_when_rain_expected():
    dry = plan("anthracnose", "chilli", SPRAY, "Plot B", forecast(), WEATHER_CFG)
    wet = plan("anthracnose", "chilli", SPRAY, "Plot B", forecast(rain_at=34), WEATHER_CFG)
    assert "dry_spray" in dry["steps"] and "rain_wait" not in dry["steps"]
    assert "rain_wait" in wet["steps"] and "dry_spray" not in wet["steps"]
    assert any("Rain expected tomorrow" in s for s in wet["en"])
    assert any("Hujan dijangka esok" in s for s in wet["ms"])


def test_plan_targets_affected_plot_and_has_3_to_5_steps():
    result = plan("anthracnose", "chilli", SPRAY, "Plot B", forecast(), WEATHER_CFG)
    assert 3 <= len(result["en"]) <= 5
    assert result["en"][0] == "Treat Plot B only – other plots do not need treatment yet."


def test_plan_never_names_products():
    result = plan("early_blight", "tomato", SPRAY, "Plot C", forecast(rain_at=9, rh=95), WEATHER_CFG)
    text = " ".join(result["en"]).lower()
    assert "registered for tomato; follow the label dose" in text
    for brand_word in ("mancozeb", "chlorothalonil", "copper", "ml/", "g/l"):
        assert brand_word not in text


def test_vector_and_hygiene_plans():
    vec = plan("leaf_curl", "chilli", {"advice_type": "vector_control"}, "Plot A", forecast(), WEATHER_CFG)
    assert "vector_check" in vec["steps"] and "vector_dry" in vec["steps"]
    hyg = plan("mosaic_virus", "tomato", {"advice_type": "hygiene"}, "Plot C", None, WEATHER_CFG)
    assert hyg["steps"][0] == "hygiene_remove"


def test_low_confidence_plan_asks_retake():
    result = plan("anthracnose", "chilli", SPRAY, "Plot B", forecast(), WEATHER_CFG, low_confidence=True)
    assert result["steps"] == ["retake", "expert"]
    assert result["en"][0].startswith("Not sure – please retake the photo")


def test_missing_forecast_is_handled():
    result = plan("anthracnose", "chilli", SPRAY, "Plot B", None, WEATHER_CFG)
    assert "no_forecast" in result["steps"]


def test_humid_spray_plan_keeps_monitor_step():
    result = plan("early_blight", "tomato", SPRAY, "Plot C", forecast(rain_at=9, rh=95), WEATHER_CFG)
    assert "remove_leaves_humid" in result["steps"] and result["steps"][-1] == "monitor" and len(result["steps"]) == 5


def test_spider_mites_get_mite_advice_not_whitefly():
    result = plan("spider_mites", "tomato", {"advice_type": "vector_control"}, "Plot C", forecast(), WEATHER_CFG)
    text = " ".join(result["en"]).lower()
    assert "mite" in text and "whitefl" not in text
