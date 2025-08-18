# app/extensions.py
from flask_migrate import Migrate
from .models import db
from flask_cors import CORS

migrate = Migrate()

def register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        supports_credentials=False,
        allow_headers=["*"],
        expose_headers=["*"],
        methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"]
    )