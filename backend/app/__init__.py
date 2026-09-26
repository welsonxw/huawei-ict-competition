from pathlib import Path

from flask import Flask
from flask_cors import CORS

from .config import ROOT_DIR, Config
from .extensions import cache, db, migrate
from .services.auth import persistent_secret


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    if app.config["CORS_ORIGINS"]:
        CORS(app, origins=app.config["CORS_ORIGINS"], supports_credentials=True)
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = persistent_secret(Path(app.config["LOCAL_STORAGE_DIR"]).parent / ".secret_key")

    db_uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if db_uri.startswith("sqlite:///"):
        Path(db_uri.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(ROOT_DIR / "backend" / "migrations"))
    cache.init_app(app)

    from . import models  # noqa: F401
    from .routes import register_routes

    register_routes(app)

    from .cli import register_cli

    register_cli(app)

    if app.config["ENABLE_SCHEDULER"]:
        from .scheduler import start_scheduler

        start_scheduler(app)
    return app
