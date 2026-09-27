from .assistant import bp as assistant_bp
from .auth import bp as auth_bp
from .control import bp as control_bp
from .fertiliser import bp as fertiliser_bp
from .game import bp as game_bp
from .health import bp as health_bp
from .iot import bp as iot_bp
from .national import bp as national_bp
from .review import bp as review_bp
from .risk import bp as risk_bp
from .scans import bp as scans_bp
from .system import bp as system_bp


def register_routes(app):
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(scans_bp, url_prefix="/api")
    app.register_blueprint(fertiliser_bp, url_prefix="/api")
    app.register_blueprint(risk_bp, url_prefix="/api")
    app.register_blueprint(national_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(review_bp, url_prefix="/api")
    app.register_blueprint(assistant_bp, url_prefix="/api")
    app.register_blueprint(system_bp, url_prefix="/api")
    app.register_blueprint(game_bp, url_prefix="/api")
    app.register_blueprint(iot_bp, url_prefix="/api")
    app.register_blueprint(control_bp, url_prefix="/api")
