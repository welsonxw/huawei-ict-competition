import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or f"sqlite:///{ROOT_DIR / 'data' / 'dev.db'}"
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    CONFIG_DIR = Path(os.getenv("CONFIG_DIR", ROOT_DIR / "config"))
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    LOCAL_STORAGE_DIR = Path(os.getenv("LOCAL_STORAGE_DIR", ROOT_DIR / "data" / "uploads"))
    OBS_ENDPOINT = os.getenv("OBS_ENDPOINT", "")
    OBS_BUCKET = os.getenv("OBS_BUCKET", "")
    OBS_ACCESS_KEY = os.getenv("OBS_ACCESS_KEY", "")
    OBS_SECRET_KEY = os.getenv("OBS_SECRET_KEY", "")
    OBS_REGION = os.getenv("OBS_REGION", "")
    PREDICTOR = os.getenv("PREDICTOR", "local")
    MODEL_DIR = Path(os.getenv("MODEL_DIR", ROOT_DIR / "ml" / "weights"))
    MODELARTS_ENDPOINT = os.getenv("MODELARTS_ENDPOINT", "")
    MODELARTS_TOKEN = os.getenv("MODELARTS_TOKEN", "")
    LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "")
    MQTT_BROKER_URL = os.getenv("MQTT_BROKER_URL", "")
    MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
    MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
    IOTDA_PRODUCT_ID = os.getenv("IOTDA_PRODUCT_ID", "")
    IOTDA_PUSH_TOKEN = os.getenv("IOTDA_PUSH_TOKEN", "")
    # Command downlink through the IoTDA application API (e.g. https://<id>.iotda-app.<region>.myhuaweicloud.com).
    IOTDA_API_ENDPOINT = os.getenv("IOTDA_API_ENDPOINT", "")
    IOTDA_PROJECT_ID = os.getenv("IOTDA_PROJECT_ID", "")
    IOTDA_IAM_TOKEN = os.getenv("IOTDA_IAM_TOKEN", "")
    ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "false").lower() == "true"
    ENABLE_DEVICE_SIM = os.getenv("ENABLE_DEVICE_SIM", "false").lower() == "true"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    REDIS_URL = "fakeredis://"
    ENABLE_SCHEDULER = False
    ENABLE_DEVICE_SIM = False
    SECRET_KEY = "test-secret"
    MQTT_BROKER_URL = ""
    IOTDA_PRODUCT_ID = ""
    IOTDA_PUSH_TOKEN = ""
    IOTDA_API_ENDPOINT = ""
    IOTDA_PROJECT_ID = ""
    IOTDA_IAM_TOKEN = ""
