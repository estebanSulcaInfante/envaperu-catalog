# app/extensions.py
from flask_migrate import Migrate
from .models import db

migrate = Migrate()

def register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
