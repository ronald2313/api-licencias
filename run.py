"""
Script de ejecución local (desarrollo)
Para producción, usar gunicorn: gunicorn -w 4 -b 0.0.0.0:$PORT "app:create_app()"

Variables de entorno requeridas:
- SECRET_KEY: Clave secreta para firmas
- DATABASE_URL: URL de PostgreSQL
- ADMIN_API_KEY: (opcional) para endpoints de admin
"""
import os
from app import create_app, db
from app.models import License, Customer, BusinessConfig, ValidationLog, Renewal

required_env = ['SECRET_KEY', 'DATABASE_URL']
missing = [var for var in required_env if not os.environ.get(var)]
if missing:
    raise RuntimeError(
        f"Faltan variables de entorno requeridas: {', '.join(missing)}"
    )

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'License': License,
        'Customer': Customer,
        'BusinessConfig': BusinessConfig,
        'ValidationLog': ValidationLog,
        'Renewal': Renewal
    }


@app.cli.command('create-db')
def create_db():
    with app.app_context():
        db.create_all()
        print('Base de datos creada exitosamente')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)