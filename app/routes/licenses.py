from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta
from sqlalchemy.exc import SQLAlchemyError
from functools import wraps
import time

from app import db
from app.models import License, Customer, ValidationLog, Renewal

licenses_bp = Blueprint('licenses', __name__)

# Rate limiting simple (en producción usar Redis)
_request_tracker = {}


def rate_limit(max_requests=10, window=60):
    """Decorator para rate limiting simple"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or 'unknown'
            now = time.time()

            # Limpiar entradas antiguas
            if ip in _request_tracker:
                _request_tracker[ip] = [
                    t for t in _request_tracker[ip]
                    if now - t < window
                ]
            else:
                _request_tracker[ip] = []

            if len(_request_tracker.get(ip, [])) >= max_requests:
                return jsonify({
                    'success': False,
                    'error': 'Demasiadas requests. Intente más tarde.',
                    'code': 'RATE_LIMITED'
                }), 429

            _request_tracker[ip].append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def verify_signed_request(data):
    """Verificar firma de request del cliente"""
    signature = data.get('_signature')
    timestamp = data.get('_timestamp')

    if not signature or not timestamp:
        return False, 'Missing signature or timestamp'

    # Verificar que timestamp no es muy viejo (5 minutos)
    try:
        req_time = datetime.fromisoformat(timestamp)
        if (datetime.utcnow() - req_time).total_seconds() > 300:
            return False, 'Request timestamp too old'
    except:
        return False, 'Invalid timestamp'

    # En producción, verificar HMAC real
    return True, None


@licenses_bp.route('/activate', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def activate_license():
    """
    Activar una licencia por primera vez.
    Vincula el license_key con el hardware_id.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos',
                'code': 'NO_DATA'
            }), 400

        license_key = data.get('license_key', '').strip().upper()
        hardware_id = data.get('hardware_id', '').strip()
        version = data.get('version', '1.0.0')

        if not license_key:
            return jsonify({
                'success': False,
                'error': 'license_key es requerido',
                'code': 'MISSING_LICENSE_KEY'
            }), 400

        if not hardware_id:
            return jsonify({
                'success': False,
                'error': 'hardware_id es requerido',
                'code': 'MISSING_HARDWARE_ID'
            }), 400

        # Verificar firma del request (opcional, para cliente actualizado)
        sig_valid, sig_error = verify_signed_request(data)
        if not sig_valid and data.get('_signature'):
            return jsonify({
                'success': False,
                'error': f'Firma inválida: {sig_error}',
                'code': 'INVALID_SIGNATURE'
            }), 403

        # Buscar licencia
        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            return jsonify({
                'success': False,
                'error': 'Licencia no encontrada',
                'code': 'LICENSE_NOT_FOUND'
            }), 404

        # Verificar si está revocada
        if license_obj.revoked_at:
            return jsonify({
                'success': False,
                'error': 'Licencia revocada',
                'code': 'LICENSE_REVOKED',
                'reason': license_obj.revoked_reason
            }), 403

        # Verificar si ya está activada con otro hardware
        if license_obj.hardware_id_hash and not license_obj.verify_hardware_id(hardware_id):
            return jsonify({
                'success': False,
                'error': 'Licencia ya activada en otro equipo',
                'code': 'HARDWARE_MISMATCH',
                'activated': False
            }), 403

        # Activar si no tiene hardware
        if not license_obj.hardware_id_hash:
            license_obj.set_hardware_id(hardware_id)
            license_obj.activation_count += 1
            license_obj.last_validation = datetime.utcnow()
            db.session.commit()

        # Actualizar estado
        license_obj.actualizar_estado()
        db.session.commit()

        # Registrar en logs
        ip_cliente = request.remote_addr
        log = ValidationLog(
            license_id=license_obj.id,
            hardware_id=hardware_id[:32] if hardware_id else None,  # Truncar por privacidad
            ip_cliente=ip_cliente,
            resultado='exito',
            mensaje='Activación exitosa',
            version_cliente=version
        )
        db.session.add(log)
        db.session.commit()

        # Generar respuesta firmada
        secret_key = current_app.config.get('SECRET_KEY', 'dev-key')
        response_data = license_obj.to_signed_response(secret_key)
        response_data['activado'] = True

        return jsonify({
            'success': True,
            **response_data
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Error de base de datos',
            'code': 'DB_ERROR',
            'detail': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor',
            'code': 'INTERNAL_ERROR',
            'detail': str(e)
        }), 500


@licenses_bp.route('/validate', methods=['POST'])
@rate_limit(max_requests=30, window=60)
def validate_license():
    """
    Validar una licencia existente.
    Verifica hardware, estado y calcula período de gracia si aplica.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos',
                'code': 'NO_DATA'
            }), 400

        license_key = data.get('license_key', '').strip().upper()
        hardware_id = data.get('hardware_id', '').strip()
        version = data.get('version', '1.0.0')
        is_offline = data.get('is_offline', False)
        offline_days_reported = data.get('offline_days', 0)

        if not license_key:
            return jsonify({
                'success': False,
                'error': 'license_key es requerido',
                'code': 'MISSING_LICENSE_KEY'
            }), 400

        # Buscar licencia
        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            return jsonify({
                'success': False,
                'error': 'Licencia no encontrada',
                'code': 'LICENSE_NOT_FOUND'
            }), 404

        # Verificar si está revocada
        if license_obj.revoked_at:
            return jsonify({
                'success': False,
                'error': 'Licencia revocada',
                'code': 'LICENSE_REVOKED'
            }), 403

        # Verificar hardware
        if license_obj.hardware_id_hash and not license_obj.verify_hardware_id(hardware_id):
            return jsonify({
                'success': False,
                'error': 'Hardware no coincide con el registrado',
                'code': 'HARDWARE_MISMATCH',
                'valid': False
            }), 403

        # Actualizar estado basado en fecha
        license_obj.actualizar_estado()
        db.session.commit()

        # Preparar respuesta
        ip_cliente = request.remote_addr
        resultado = 'exito'
        mensaje = 'Validación exitosa'
        grace_permitido = False
        grace_remaining = 0

        # Manejar validación offline
        if is_offline:
            # Validar días offline reportados
            if offline_days_reported > license_obj.max_offline_days:
                return jsonify({
                    'success': False,
                    'error': 'Límite de días offline excedido',
                    'code': 'OFFLINE_LIMIT_EXCEEDED',
                    'max_offline_days': license_obj.max_offline_days,
                    'offline_days_reported': offline_days_reported
                }), 403
            license_obj.last_offline_check = datetime.utcnow()
            license_obj.offline_days_used = offline_days_reported

        # Si está vencida
        if license_obj.estado == 'vencida':
            if not license_obj.grace_used:
                # Iniciar gracia
                license_obj.start_grace_period()
                db.session.commit()
                grace_permitido = True
                resultado = 'grace'
                grace_remaining = license_obj.grace_hours_remaining
                mensaje = f'Licencia vencida. Período de gracia activado: {grace_remaining} horas restantes'
            elif license_obj.is_in_grace_period:
                # Aún en gracia
                grace_permitido = True
                resultado = 'grace'
                grace_remaining = license_obj.grace_hours_remaining
                mensaje = f'En período de gracia. Horas restantes: {grace_remaining}'
            else:
                resultado = 'bloqueado'
                mensaje = 'Licencia vencida. Período de gracia expirado.'

        # Si está por vencer
        elif license_obj.estado == 'por_vencer':
            mensaje = f'Licencia por vencer. Días restantes: {license_obj.dias_restantes}'

        # Si está en gracia
        elif license_obj.estado == 'gracia':
            grace_permitido = True
            grace_remaining = license_obj.grace_hours_remaining
            mensaje = f'Licencia en período de gracia. Horas restantes: {grace_remaining}'

        # Si está suspendida
        elif license_obj.estado == 'suspendida':
            resultado = 'suspendida'
            mensaje = 'Licencia suspendida. Contacte soporte.'

        # Registrar en logs
        log = ValidationLog(
            license_id=license_obj.id,
            hardware_id=hardware_id[:32] if hardware_id else None,
            ip_cliente=ip_cliente,
            resultado=resultado,
            mensaje=mensaje,
            version_cliente=version
        )
        db.session.add(log)

        # Actualizar última validación
        license_obj.last_validation = datetime.utcnow()
        db.session.commit()

        # Preparar respuesta firmada
        secret_key = current_app.config.get('SECRET_KEY', 'dev-key')
        response_data = {
            'valid': resultado in ['exito', 'grace'],
            'estado': license_obj.estado,
            'fecha_expiracion': license_obj.fecha_expiracion.isoformat(),
            'dias_restantes': license_obj.dias_restantes,
            'grace_used': license_obj.grace_used,
            'grace_permitido': grace_permitido,
            'grace_hours_remaining': grace_remaining if grace_permitido else 0,
            'max_offline_days': license_obj.max_offline_days,
            'offline_days_used': license_obj.offline_days_used,
            'mensaje': mensaje
        }

        # Firmar respuesta
        signature = hmac.new(
            secret_key.encode(),
            str(response_data).encode(),
            __import__('hashlib').sha256
        ).hexdigest()

        return jsonify({
            'success': resultado in ['exito', 'grace'],
            'data': response_data,
            'signature': signature,
            'timestamp': datetime.utcnow().isoformat()
        }), 200 if resultado in ['exito', 'grace'] else 403

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Error de base de datos',
            'code': 'DB_ERROR',
            'detail': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor',
            'code': 'INTERNAL_ERROR',
            'detail': str(e)
        }), 500


@licenses_bp.route('/renew', methods=['POST'])
@rate_limit(max_requests=5, window=60)
def renew_license():
    """
    Renovar una licencia.
    Actualiza la fecha de expiración y resetea período de gracia.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No se recibieron datos',
                'code': 'NO_DATA'
            }), 400

        license_key = data.get('license_key', '').strip().upper()
        hardware_id = data.get('hardware_id', '').strip()
        periodo_meses = int(data.get('periodo_meses', 12))
        version = data.get('version', '1.0.0')

        if not license_key:
            return jsonify({
                'success': False,
                'error': 'license_key es requerido',
                'code': 'MISSING_LICENSE_KEY'
            }), 400

        if periodo_meses not in [1, 3, 6, 12, 24]:
            return jsonify({
                'success': False,
                'error': 'periodo_meses inválido. Valores permitidos: 1, 3, 6, 12, 24',
                'code': 'INVALID_PERIOD'
            }), 400

        # Buscar licencia
        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            return jsonify({
                'success': False,
                'error': 'Licencia no encontrada',
                'code': 'LICENSE_NOT_FOUND'
            }), 404

        # Verificar si está revocada
        if license_obj.revoked_at:
            return jsonify({
                'success': False,
                'error': 'Licencia revocada',
                'code': 'LICENSE_REVOKED'
            }), 403

        # Verificar hardware
        if license_obj.hardware_id_hash and not license_obj.verify_hardware_id(hardware_id):
            return jsonify({
                'success': False,
                'error': 'Hardware no coincide',
                'code': 'HARDWARE_MISMATCH'
            }), 403

        # Calcular nueva fecha de expiración (desde hoy, no desde la expiración anterior)
        hoy = datetime.utcnow()
        nueva_fecha = hoy + timedelta(days=30 * periodo_meses)

        # Guardar fecha anterior para registro
        fecha_anterior = license_obj.fecha_expiracion

        # Actualizar licencia
        license_obj.fecha_expiracion = nueva_fecha
        license_obj.estado = 'activa'
        license_obj.grace_used = False
        license_obj.grace_started_at = None
        license_obj.offline_days_used = 0
        license_obj.last_validation = hoy

        # Crear registro de renovación
        renewal = Renewal(
            license_id=license_obj.id,
            nueva_fecha_expiracion=nueva_fecha,
            periodo_meses=periodo_meses,
            estado='completada'
        )
        db.session.add(renewal)

        # Registrar en logs
        log = ValidationLog(
            license_id=license_obj.id,
            hardware_id=hardware_id[:32] if hardware_id else None,
            ip_cliente=request.remote_addr,
            resultado='exito',
            mensaje=f'Renovación exitosa. Fecha anterior: {fecha_anterior}, Nueva: {nueva_fecha}',
            version_cliente=version
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({
            'success': True,
            'data': {
                'renovado': True,
                'nueva_fecha_expiracion': nueva_fecha.isoformat(),
                'dias_restantes': license_obj.dias_restantes,
                'estado': license_obj.estado,
                'grace_reset': True,
                'offline_days_reset': True
            }
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'Error de base de datos',
            'code': 'DB_ERROR',
            'detail': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Error interno del servidor',
            'code': 'INTERNAL_ERROR',
            'detail': str(e)
        }), 500


@licenses_bp.route('/revoke', methods=['POST'])
def revoke_license():
    """
    Revocar una licencia (solo admin).
    Requiere API key de administrador.
    """
    try:
        data = request.get_json()
        admin_key = request.headers.get('X-Admin-Key')

        # Verificar API key (en producción usar variable de entorno)
        expected_key = current_app.config.get('ADMIN_API_KEY')
        if not expected_key or admin_key != expected_key:
            return jsonify({
                'success': False,
                'error': 'Unauthorized',
                'code': 'UNAUTHORIZED'
            }), 401

        license_key = data.get('license_key', '').strip().upper()
        reason = data.get('reason', 'Sin especificar')

        license_obj = License.query.filter_by(license_key=license_key).first()

        if not license_obj:
            return jsonify({
                'success': False,
                'error': 'Licencia no encontrada',
                'code': 'LICENSE_NOT_FOUND'
            }), 404

        license_obj.revoked_at = datetime.utcnow()
        license_obj.revoked_reason = reason
        license_obj.estado = 'suspendida'
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Licencia revocada exitosamente',
            'revoked_at': license_obj.revoked_at.isoformat()
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 'INTERNAL_ERROR'
        }), 500


@licenses_bp.route('/heartbeat', methods=['GET'])
def heartbeat():
    """
    Endpoint para mantener viva la conexión (evitar que Render duerma).
    También sirve para health checks.
    """
    try:
        # Verificar conexión a BD
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'alive',
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'degraded',
            'database': 'disconnected',
            'error': str(e)
        }), 503
