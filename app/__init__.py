from flask import Flask
from .config import get_config
from .extensions import register_extensions
from .api import register_blueprints  # no agrega endpoints, solo estructura
from .models import db  # ← añadimos la instancia SQLAlchemy

def create_app(env_name: str | None = None) -> Flask:
    app = Flask(__name__)

    # Config
    cfg = get_config(env_name)
    app.config.from_object(cfg)

    # Extensiones (DB, Migrate, etc.)
    register_extensions(app)

    # Crear todas las tablas si no existen (solo entorno de pruebas / desarrollo)
    with app.app_context():
        db.create_all()

    # Blueprints vacíos (estructura)
    register_blueprints(app)

    # Errores genéricos (sin lógica)
    @app.errorhandler(404)
    def not_found(_e):
        return {"error": "not found"}, 404

    @app.errorhandler(500)
    def server_error(_e):
        return {"error": "server error"}, 500

    return app
