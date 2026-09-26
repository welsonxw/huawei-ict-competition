from pathlib import Path

from flask import Flask
from flask_cors import CORS

from .config import ROOT_DIR, Config
from .extensions import cache, db, migrate


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    if app.config["CORS_ORIGINS"]:
        CORS(app, origins=app.config["CORS_ORIGINS"])

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
    return app
