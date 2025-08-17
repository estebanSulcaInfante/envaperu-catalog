from flask import Blueprint

def create_api_bp():
    api_bp = Blueprint("api", __name__, url_prefix="/api")

    from .auth import auth_bp
    from .catalogo import catalogo_bp
    from .clientes import clientes_bp      
    from .productos import productos_bp    
    
    api_bp.register_blueprint(auth_bp)
    api_bp.register_blueprint(catalogo_bp)
    api_bp.register_blueprint(clientes_bp)     # <-- NUEVO
    api_bp.register_blueprint(productos_bp)    # <-- NUEVO
    return api_bp

def register_blueprints(app):
    api_bp = create_api_bp()
    app.register_blueprint(api_bp)
