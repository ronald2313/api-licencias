from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

from config import config

# Extensiones
db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name='default'):
    """Factory de la aplicación"""

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)

    # CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    # Registrar blueprints
    from app.routes import licenses_bp, config_bp
    app.register_blueprint(licenses_bp, url_prefix='/api/v1')
    app.register_blueprint(config_bp, url_prefix='/api/v1')

    # Health check
    @app.route('/health')
    def health_check():
        return {'status': 'ok', 'service': 'license-api'}, 200

    @app.route('/')
    def index():
        return {
            'service': 'API de Licencias - Sistema de Facturación',
            'version': '1.0.0',
            'endpoints': {
                'activate': 'POST /api/v1/activate',
                'validate': 'POST /api/v1/validate',
                'renew': 'POST /api/v1/renew',
                'business_config': 'GET /api/v1/business-config'
            }
        }, 200

    return app
