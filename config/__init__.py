import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración base"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-cambiar-en-produccion'

    # Base de datos
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:postgres@localhost:5432/licencias_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CORS
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')

    # Configuración de gracia
    GRACE_PERIOD_HOURS = int(os.environ.get('GRACE_PERIOD_HOURS', 24))

    # Puerto
    PORT = int(os.environ.get('PORT', 5001))


class DevelopmentConfig(Config):
    """Configuración desarrollo"""
    DEBUG = True
    REQUIRE_HTTPS = False


class ProductionConfig(Config):
    """Configuración producción"""
    DEBUG = False
    REQUIRE_HTTPS = True


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
