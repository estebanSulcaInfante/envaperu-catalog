from flask import Blueprint

def create_api_bp():
    api_bp = Blueprint("api", __name__, url_prefix="/api")

    from .auth import auth_bp
    from .catalogo import catalogo_bp
    from .clientes import clientes_bp      
    from .productos import productos_bp    
    from .sesiones import sesiones_bp
    from .versiones import versiones_bp
    
    api_bp.register_blueprint(auth_bp)
    api_bp.register_blueprint(catalogo_bp)
    api_bp.register_blueprint(clientes_bp)     
    api_bp.register_blueprint(productos_bp)    
    api_bp.register_blueprint(sesiones_bp)
    api_bp.register_blueprint(versiones_bp)
    
    return api_bp

def register_blueprints(app):
    api_bp = create_api_bp()
    app.register_blueprint(api_bp)
