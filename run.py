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

# Validar variables de entorno mínimas
required_env = ['SECRET_KEY', 'DATABASE_URL']
missing = [var for var in required_env if not os.environ.get(var)]
if missing:
    print(f"ERROR: Faltan variables de entorno requeridas: {', '.join(missing)}")
    print("Crea un archivo .env con estos valores")
    exit(1)

app = create_app(os.environ.get('FLASK_ENV', 'development'))


@app.shell_context_processor
def make_shell_context():
    """Contexto para flask shell"""
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
    """Crear tablas de base de datos"""
    with app.app_context():
        db.create_all()
        print('Base de datos creada exitosamente')


@app.cli.command('seed-db')
def seed_db():
    """Crear datos de prueba"""
    from datetime import datetime, timedelta

    with app.app_context():
        # Crear cliente de prueba
        customer = Customer(
            nombre='Tienda de Prueba',
            email='prueba@tienda.com',
            telefono='809-555-0000',
            direccion='Calle Principal #123'
        )
        db.session.add(customer)
        db.session.flush()

        # Crear licencia de prueba
        license = License(
            license_key='LIC-TEST-001',
            customer_id=customer.id,
            fecha_inicio=datetime.utcnow(),
            fecha_expiracion=datetime.utcnow() + timedelta(days=365),
            estado='activa',
            grace_used=False
        )
        db.session.add(license)

        # Crear config del negocio
        config = BusinessConfig(
            customer_id=customer.id,
            nombre_negocio='Tienda Test',
            telefono='809-555-0000',
            direccion='Calle Principal #123',
            rnc_cedula='001-1234567-8',
            email='tienda@email.com',
            mensaje_factura='Gracias por su preferencia'
        )
        db.session.add(config)

        db.session.commit()
        print('Datos de prueba creados:')
        print(f'  License Key: LIC-TEST-001')
        print(f'  Expira: {license.fecha_expiracion}')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
