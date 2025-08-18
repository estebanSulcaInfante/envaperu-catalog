# app/__init__.py
from flask import Flask
from .config import get_config
from .extensions import register_extensions
from .api import register_blueprints
# NO importes db para crear tablas aquí; el test se encarga
# from .models import db  # <- ya no lo necesitamos en este módulo

def create_app(env_name: str | None = None, config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)

    # Carga config base (por env_name)
    cfg = get_config(env_name)
    app.config.from_object(cfg)

    # Permite overrides (tests pasan su SQLALCHEMY_DATABASE_URI aquí)
    if config_overrides:
        app.config.update(config_overrides)

    # Inicializa extensiones y registra blueprints
    register_extensions(app)


    
    register_blueprints(app)

    # Errores genéricos
    @app.errorhandler(404)
    def not_found(_e):
        return {"error": "not found"}, 404

    @app.errorhandler(500)
    def server_error(_e):
        # En testing, Flask maneja tracebacks, no te preocupes
        return {"error": "server error"}, 500


    # --- CLI para crear tablas SIN Alembic ---
    @app.cli.command("init-db")
    def init_db_command():
        """Crea todas las tablas definidas en los modelos."""
        from .models import db  # import local para evitar ciclos
        with app.app_context():
            db.create_all()
        print("✔ Tablas creadas")
        
    return app
