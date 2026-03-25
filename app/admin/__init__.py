import os
from flask import Flask
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

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SECRET_KEY"] = secret_key
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    CORS(app)
    db.init_app(app)
    migrate.init_app(app, db)

    from app.models import License, Customer, BusinessConfig, ValidationLog, Renewal
    from app.routes import register_routes
    from app.admin import admin_bp

    register_routes(app)
    app.register_blueprint(admin_bp)

    @app.route("/api/test", methods=["GET"])
    def test_api():
        return {"ok": True}, 200

    return app