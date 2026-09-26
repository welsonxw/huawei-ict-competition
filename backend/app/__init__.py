from flask import Flask
from flask_cors import CORS

from .config import ROOT_DIR, Config
from .extensions import cache, db, migrate


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    CORS(app)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(ROOT_DIR / "backend" / "migrations"))
    cache.init_app(app)

    from . import models  # noqa: F401
    from .routes import register_routes

    register_routes(app)
    return app
