from flask import Blueprint, request, jsonify
from app.models import License, BusinessConfig

config_bp = Blueprint('config', __name__)


@config_bp.route('/business-config', methods=['GET'])
def get_business_config():
    """
    Obtener la configuración del negocio asociada a una licencia.
    El license_key se puede pasar como header Authorization o query param.
    """
    # Intentar obtener de header primero
    auth_header = request.headers.get('Authorization', '')
    license_key = None

    if auth_header.startswith('Bearer '):
        license_key = auth_header[7:]
    else:
        # Intentar de query param
        license_key = request.args.get('license_key')

    if not license_key:
        return jsonify({'error': 'license_key requerido (header Authorization o query param)'}), 401

    # Buscar licencia
    license = License.query.filter_by(license_key=license_key).first()

    if not license:
        return jsonify({'error': 'Licencia no encontrada'}), 404

    # Verificar que la licencia esté activa (o en gracia)
    if license.estado not in ['activa', 'por_vencer'] and license.estado != 'vencida':
        return jsonify({'error': 'Licencia no activa'}), 403

    # Obtener configuración del negocio
    config = BusinessConfig.query.filter_by(customer_id=license.customer_id).first()

    if not config:
        # Si no existe, devolver valores por defecto basados en el cliente
        customer = license.customer
        return jsonify({
            'nombre_negocio': customer.nombre if customer else 'Mi Negocio',
            'telefono': customer.telefono if customer else '',
            'direccion': customer.direccion if customer else '',
            'rnc_cedula': '',
            'email': customer.email if customer else '',
            'logo_url': None,
            'mensaje_factura': 'Gracias por su preferencia',
            'updated_at': None
        }), 200

    return jsonify(config.to_dict()), 200


# ============================================
# ENDPOINTS DE ADMINISTRACIÓN
# (Estos serían usados por el panel admin)
# ============================================

@config_bp.route('/licenses', methods=['GET'])
def list_licenses():
    """Listar todas las licencias (para panel admin)"""
    licenses = License.query.all()
    return jsonify([lic.to_dict(include_customer=True) for lic in licenses]), 200


@config_bp.route('/licenses/<int:license_id>', methods=['GET'])
def get_license(license_id):
    """Obtener detalle de una licencia"""
    license = License.query.get_or_404(license_id)
    return jsonify(license.to_dict(include_customer=True)), 200


@config_bp.route('/customers', methods=['GET'])
def list_customers():
    """Listar todos los clientes"""
    customers = Customer.query.all()
    return jsonify([c.to_dict() for c in customers]), 200


@config_bp.route('/customers', methods=['POST'])
def create_customer():
    """Crear un nuevo cliente"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No se recibieron datos'}), 400

    customer = Customer(
        nombre=data.get('nombre'),
        email=data.get('email'),
        telefono=data.get('telefono'),
        direccion=data.get('direccion')
    )

    db.session.add(customer)
    db.session.commit()

    return jsonify(customer.to_dict()), 201


@config_bp.route('/licenses', methods=['POST'])
def create_license():
    """Crear una nueva licencia (para panel admin)"""
    from datetime import datetime, timedelta
    from app.models import License, Customer

    data = request.get_json()

    if not data:
        return jsonify({'error': 'No se recibieron datos'}), 400

    customer_id = data.get('customer_id')
    license_key = data.get('license_key')
    periodo_meses = data.get('periodo_meses', 12)

    if not customer_id or not license_key:
        return jsonify({'error': 'customer_id y license_key son requeridos'}), 400

    # Verificar que el cliente existe
    customer = Customer.query.get(customer_id)
    if not customer:
        return jsonify({'error': 'Cliente no encontrado'}), 404

    # Verificar que la licencia no exista
    existing = License.query.filter_by(license_key=license_key).first()
    if existing:
        return jsonify({'error': 'License key ya existe'}), 400

    # Calcular fechas
    hoy = datetime.utcnow()
    fecha_exp = hoy + timedelta(days=30 * periodo_meses)

    license = License(
        license_key=license_key,
        customer_id=customer_id,
        fecha_inicio=hoy,
        fecha_expiracion=fecha_exp,
        estado='activa'
    )

    db.session.add(license)

    # Crear business_config por defecto
    config = BusinessConfig(
        customer_id=customer_id,
        nombre_negocio=customer.nombre or 'Mi Negocio',
        email=customer.email
    )
    db.session.add(config)

    db.session.commit()

    return jsonify(license.to_dict(include_customer=True)), 201


# Importar db aquí para evitar circular import
from app import db
from app.models import Customer
