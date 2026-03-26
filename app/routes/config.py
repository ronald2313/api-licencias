from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models import License, BusinessConfig, Customer

config_bp = Blueprint('config', __name__)


@config_bp.route('/business-config', methods=['GET'])
def get_business_config():
    """
    Obtener la configuración del negocio asociada a una licencia.
    El license_key se puede pasar como header Authorization o query param.
    """
    try:
        # Intentar obtener de header primero
        auth_header = request.headers.get('Authorization', '')
        license_key = None

        if auth_header.startswith('Bearer '):
            license_key = auth_header[7:].strip()
        else:
            # Intentar de query param
            license_key = request.args.get('license_key')

        if not license_key:
            return jsonify({
                'success': False,
                'error': 'license_key requerido (header Authorization: Bearer <key> o query param)',
                'code': 'MISSING_LICENSE_KEY'
            }), 401

        # Buscar licencia con manejo de errores de base de datos
        try:
            license_obj = License.query.filter_by(license_key=license_key.upper()).first()
        except SQLAlchemyError as e:
            return jsonify({
                'success': False,
                'error': 'Error de base de datos al buscar licencia',
                'detail': str(e)
            }), 500

        if not license_obj:
            return jsonify({
                'success': False,
                'error': 'Licencia no encontrada',
                'code': 'LICENSE_NOT_FOUND'
            }), 404

        # Verificar que la licencia esté activa o por vencer
        if license_obj.estado not in ['activa', 'por_vencer', 'gracia']:
            return jsonify({
                'success': False,
                'error': 'Licencia no activa',
                'code': 'LICENSE_INACTIVE',
                'estado': license_obj.estado,
                'dias_restantes': license_obj.dias_restantes
            }), 403

        # Obtener el cliente asociado de forma segura
        customer = license_obj.customer

        if not customer:
            return jsonify({
                'success': False,
                'error': 'Cliente asociado a la licencia no encontrado',
                'code': 'CUSTOMER_NOT_FOUND'
            }), 404

        # Obtener configuración del negocio de forma segura
        try:
            config = BusinessConfig.query.filter_by(customer_id=license_obj.customer_id).first()
        except SQLAlchemyError as e:
            return jsonify({
                'success': False,
                'error': 'Error de base de datos al buscar configuración',
                'detail': str(e)
            }), 500

        if not config:
            # Si no existe configuración, devolver valores por defecto basados en el cliente
            response_data = {
                'success': True,
                'data': {
                    'nombre_negocio': customer.nombre or 'Mi Negocio',
                    'telefono': customer.telefono or '',
                    'direccion': customer.direccion or '',
                    'rnc_cedula': '',
                    'email': customer.email or '',
                    'logo_url': None,
                    'mensaje_factura': 'Gracias por su preferencia',
                    'updated_at': None
                },
                'source': 'default_from_customer'
            }
            return jsonify(response_data), 200

        # Configuración existe - devolverla
        return jsonify({
            'success': True,
            'data': {
                'nombre_negocio': config.nombre_negocio,
                'telefono': config.telefono,
                'direccion': config.direccion,
                'rnc_cedula': config.rnc_cedula,
                'email': config.email,
                'logo_url': config.logo_url,
                'mensaje_factura': config.mensaje_factura,
                'updated_at': config.updated_at.isoformat() if config.updated_at else None
            },
            'source': 'database'
        }), 200

    except Exception as e:
        # Captura cualquier error inesperado
        import traceback
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor',
            'code': 'INTERNAL_ERROR',
            'detail': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================
# ENDPOINTS DE ADMINISTRACIÓN
# (Estos serían usados por el panel admin)
# ============================================

@config_bp.route('/licenses', methods=['GET'])
def list_licenses():
    """Listar todas las licencias (para panel admin)"""
    try:
        licenses = License.query.all()
        return jsonify({
            'success': True,
            'data': [lic.to_dict(include_customer=True) for lic in licenses]
        }), 200
    except SQLAlchemyError as e:
        return jsonify({
            'success': False,
            'error': 'Error de base de datos',
            'detail': str(e)
        }), 500


@config_bp.route('/licenses/<int:license_id>', methods=['GET'])
def get_license(license_id):
    """Obtener detalle de una licencia"""
    try:
        license_obj = License.query.get(license_id)
        if not license_obj:
            return jsonify({
                'success': False,
                'error': 'Licencia no encontrada'
            }), 404
        return jsonify({
            'success': True,
            'data': license_obj.to_dict(include_customer=True)
        }), 200
    except SQLAlchemyError as e:
        return jsonify({
            'success': False,
            'error': 'Error de base de datos',
            'detail': str(e)
        }), 500


@config_bp.route('/customers', methods=['GET'])
def list_customers():
    """Listar todos los clientes"""
    try:
        customers = Customer.query.all()
        return jsonify({
            'success': True,
            'data': [c.to_dict() for c in customers]
        }), 200
    except SQLAlchemyError as e:
        return jsonify({
            'success': False,
            'error': 'Error de base de datos',
            'detail': str(e)
        }), 500


@config_bp.route('/customers', methods=['POST'])
def create_customer():
    """Crear un nuevo cliente"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos'
            }), 400

        # Validaciones
        nombre = data.get('nombre', '').strip()
        email = data.get('email', '').strip()

        if not nombre:
            return jsonify({
                'success': False,
                'error': 'El nombre es requerido'
            }), 400

        if not email:
            return jsonify({
                'success': False,
                'error': 'El email es requerido'
            }), 400

        # Verificar email único
        existing = Customer.query.filter_by(email=email).first()
        if existing:
            return jsonify({
                'success': False,
                'error': 'Ya existe un cliente con ese email'
            }), 400

        customer = Customer(
            nombre=nombre,
            email=email,
            telefono=data.get('telefono', ''),
            direccion=data.get('direccion', '')
        )

        db.session.add(customer)
        db.session.commit()

        return jsonify({
            'success': True,
            'data': customer.to_dict()
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Error de base de datos',
            'detail': str(e)
        }), 500


@config_bp.route('/licenses', methods=['POST'])
def create_license():
    """Crear una nueva licencia (para panel admin)"""
    from datetime import datetime, timedelta

    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos'
            }), 400

        customer_id = data.get('customer_id')
        license_key = data.get('license_key', '').strip()
        periodo_meses = data.get('periodo_meses', 12)

        if not customer_id:
            return jsonify({
                'success': False,
                'error': 'customer_id es requerido'
            }), 400

        if not license_key:
            return jsonify({
                'success': False,
                'error': 'license_key es requerido'
            }), 400

        # Verificar que el cliente existe
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({
                'success': False,
                'error': 'Cliente no encontrado'
            }), 404

        # Verificar que la licencia no exista
        existing = License.query.filter_by(license_key=license_key).first()
        if existing:
            return jsonify({
                'success': False,
                'error': 'License key ya existe'
            }), 400

        # Calcular fechas
        hoy = datetime.utcnow()
        fecha_exp = hoy + timedelta(days=30 * int(periodo_meses))

        license_obj = License(
            license_key=license_key,
            customer_id=customer_id,
            fecha_inicio=hoy,
            fecha_expiracion=fecha_exp,
            estado='activa'
        )

        db.session.add(license_obj)

        # Crear business_config por defecto (solo si no existe)
        existing_config = BusinessConfig.query.filter_by(customer_id=customer_id).first()
        if not existing_config:
            config = BusinessConfig(
                customer_id=customer_id,
                nombre_negocio=customer.nombre or 'Mi Negocio',
                email=customer.email
            )
            db.session.add(config)

        db.session.commit()

        return jsonify({
            'success': True,
            'data': license_obj.to_dict(include_customer=True)
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Error de base de datos',
            'detail': str(e)
        }), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Error interno',
            'detail': str(e)
        }), 500
