from .health import bp as health_bp
from .scans import bp as scans_bp


def register_routes(app):
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(scans_bp, url_prefix="/api")
