from .fertiliser import bp as fertiliser_bp
from .health import bp as health_bp
from .national import bp as national_bp
from .risk import bp as risk_bp
from .scans import bp as scans_bp


def register_routes(app):
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(scans_bp, url_prefix="/api")
    app.register_blueprint(fertiliser_bp, url_prefix="/api")
    app.register_blueprint(risk_bp, url_prefix="/api")
    app.register_blueprint(national_bp, url_prefix="/api")
