from flask_migrate import Migrate
from .models import db  # usa el db de tus modelos

migrate = Migrate()

def register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
