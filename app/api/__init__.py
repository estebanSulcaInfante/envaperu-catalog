from flask import Blueprint

def create_api_bp():
    api_bp = Blueprint("api", __name__, url_prefix="/api")

    # Importa y ANEXA sub-blueprints ANTES de registrar api_bp en la app
    from .auth import auth_bp
    from .catalogo import catalogo_bp

    api_bp.register_blueprint(auth_bp)
    api_bp.register_blueprint(catalogo_bp)
    return api_bp

def register_blueprints(app):
    api_bp = create_api_bp()
    app.register_blueprint(api_bp)
