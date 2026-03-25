import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración base"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY debe estar definida en variables de entorno")

    # Base de datos
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("DATABASE_URL debe estar definida en variables de entorno")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Verificar conexión antes de usar
        'pool_recycle': 300,    # Reciclar conexiones cada 5 minutos
    }

    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

    # Configuración de gracia (horas)
    GRACE_PERIOD_HOURS = int(os.environ.get('GRACE_PERIOD_HOURS', 24))
    MAX_OFFLINE_DAYS = int(os.environ.get('MAX_OFFLINE_DAYS', 1))

    # Seguridad
    ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')
    REQUIRE_SIGNED_REQUESTS = os.environ.get('REQUIRE_SIGNED_REQUESTS', 'false').lower() == 'true'

    # Panel Admin Web
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

    # Puerto
    PORT = int(os.environ.get('PORT', 5001))

    # Rate limiting
    RATE_LIMIT_ENABLED = os.environ.get('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    RATE_LIMIT_REQUESTS = int(os.environ.get('RATE_LIMIT_REQUESTS', 30))
    RATE_LIMIT_WINDOW = int(os.environ.get('RATE_LIMIT_WINDOW', 60))


class DevelopmentConfig(Config):
    """Configuración desarrollo"""
    DEBUG = True
    REQUIRE_HTTPS = False
    TESTING = False


class ProductionConfig(Config):
    """Configuración producción"""
    DEBUG = False
    REQUIRE_HTTPS = True
    TESTING = False

    # En producción, requerir firma para requests sensibles
    REQUIRE_SIGNED_REQUESTS = True


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
