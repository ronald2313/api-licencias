import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    database_url = os.environ.get("DATABASE_URL")
    secret_key = os.environ.get("SECRET_KEY")

    if not database_url:
        raise RuntimeError("Falta la variable de entorno DATABASE_URL")

    if not secret_key:
        raise RuntimeError("Falta la variable de entorno SECRET_KEY")

    # Compatibilidad con algunos providers antiguos
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    CORS(app)

    db.init_app(app)
    migrate.init_app(app, db)

    # Importar modelos después de init_app para registrar metadata
    from app.models import License, Customer, BusinessConfig, ValidationLog, Renewal  # noqa: F401

    # Registrar blueprints de la API
    from app.routes import licenses_bp, config_bp
    app.register_blueprint(licenses_bp, url_prefix='/api/v1')
    app.register_blueprint(config_bp, url_prefix='/api/v1')

    # Registrar blueprint del panel admin
    from app.admin import admin_bp
    app.register_blueprint(admin_bp)

    @app.route("/")
    def home():
        return jsonify({
            "status": "ok",
            "message": "API de licencias funcionando",
            "endpoints": {
                "api": "/api/v1",
                "admin": "/admin"
            }
        }), 200

    @app.route("/health")
    def health():
        return jsonify({"status": "healthy"}), 200

    return app
