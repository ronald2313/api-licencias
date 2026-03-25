from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from app import db
from app.models import License, Customer, ValidationLog, Renewal

licenses_bp = Blueprint('licenses', __name__)


@licenses_bp.route('/activate', methods=['POST'])
def activate_license():
    """
    Activar una licencia por primera vez.
    Vincula el license_key con el hardware_id.
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No se recibieron datos'}), 400

    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')
    version = data.get('version', '1.0.0')

    if not license_key:
        return jsonify({'error': 'license_key es requerido'}), 400

    # Buscar licencia
    license = License.query.filter_by(license_key=license_key).first()

    if not license:
        return jsonify({'error': 'Licencia no encontrada'}), 404

    # Verificar si ya está activada con otro hardware
    if license.hardware_id and license.hardware_id != hardware_id:
        return jsonify({
            'error': 'Licencia ya activada en otro equipo',
            'activated': False
        }), 403

    # Activar si no tiene hardware
    if not license.hardware_id:
        license.hardware_id = hardware_id
        license.last_validation = datetime.utcnow()
        db.session.commit()

    # Actualizar estado
    license.actualizar_estado()
    db.session.commit()

    # Registrar en logs
    ip_cliente = request.remote_addr
    log = ValidationLog(
        license_id=license.id,
        hardware_id=hardware_id,
        ip_cliente=ip_cliente,
        resultado='exito',
        mensaje='Activación exitosa',
        version_cliente=version
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'activado': True,
        'license_key': license.license_key,
        'hardware_id': license.hardware_id,
        'fecha_expiracion': license.fecha_expiracion.isoformat(),
        'estado': license.estado,
        'dias_restantes': license.dias_restantes
    }), 200


@licenses_bp.route('/validate', methods=['POST'])
def validate_license():
    """
    Validar una licencia existente.
    Verifica hardware, estado y calcula período de gracia si aplica.
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No se recibieron datos'}), 400

    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')
    version = data.get('version', '1.0.0')

    if not license_key:
        return jsonify({'error': 'license_key es requerido'}), 400

    # Buscar licencia
    license = License.query.filter_by(license_key=license_key).first()

    if not license:
        return jsonify({'error': 'Licencia no encontrada'}), 404

    # Verificar hardware (si ya está vinculada)
    if license.hardware_id and license.hardware_id != hardware_id:
        return jsonify({
            'valid': False,
            'error': 'Hardware no coincide con el registrado'
        }), 403

    # Actualizar estado basado en fecha
    license.actualizar_estado()
    db.session.commit()

    # Preparar respuesta
    ip_cliente = request.remote_addr
    resultado = 'exito'
    mensaje = 'Validación exitosa'
    grace_permitido = False

    # Si está vencida
    if license.estado == 'vencida':
        if not license.grace_used:
            grace_permitido = True
            resultado = 'grace'
            mensaje = 'Licencia vencida. Período de gracia disponible: 24 horas'
        else:
            resultado = 'bloqueado'
            mensaje = 'Licencia vencida. Período de gracia ya usado.'

    # Si está por vencer
    elif license.estado == 'por_vencer':
        mensaje = f'Licencia por vencer. Días restantes: {license.dias_restantes}'

    # Si está suspendida
    elif license.estado == 'suspendida':
        resultado = 'suspendida'
        mensaje = 'Licencia suspendida. Contacte soporte.'

    # Registrar en logs
    log = ValidationLog(
        license_id=license.id,
        hardware_id=hardware_id,
        ip_cliente=ip_cliente,
        resultado=resultado,
        mensaje=mensaje,
        version_cliente=version
    )
    db.session.add(log)

    # Actualizar última validación
    license.last_validation = datetime.utcnow()
    db.session.commit()

    # Preparar respuesta
    response = {
        'valid': resultado in ['exito', 'grace'],
        'estado': license.estado,
        'fecha_expiracion': license.fecha_expiracion.isoformat(),
        'dias_restantes': license.dias_restantes,
        'grace_used': license.grace_used,
        'grace_permitido': grace_permitido,
        'mensaje': mensaje
    }

    return jsonify(response), 200 if resultado in ['exito', 'grace'] else 403


@licenses_bp.route('/renew', methods=['POST'])
def renew_license():
    """
    Renovar una licencia.
    Actualiza la fecha de expiración y marca grace_used como disponible nuevamente.
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No se recibieron datos'}), 400

    license_key = data.get('license_key')
    hardware_id = data.get('hardware_id')
    periodo_meses = data.get('periodo_meses', 12)

    if not license_key:
        return jsonify({'error': 'license_key es requerido'}), 400

    # Buscar licencia
    license = License.query.filter_by(license_key=license_key).first()

    if not license:
        return jsonify({'error': 'Licencia no encontrada'}), 404

    # Verificar hardware
    if license.hardware_id and license.hardware_id != hardware_id:
        return jsonify({'error': 'Hardware no coincide'}), 403

    # Calcular nueva fecha de expiración
    hoy = datetime.utcnow()
    nueva_fecha = hoy + timedelta(days=30 * periodo_meses)

    # Actualizar licencia
    license.fecha_expiracion = nueva_fecha
    license.estado = 'activa'
    license.grace_used = False  # Resetear período de gracia
    license.last_validation = hoy

    # Crear registro de renovación
    renewal = Renewal(
        license_id=license.id,
        nueva_fecha_expiracion=nueva_fecha,
        periodo_meses=periodo_meses
    )
    db.session.add(renewal)
    db.session.commit()

    return jsonify({
        'renovado': True,
        'nueva_fecha_expiracion': nueva_fecha.isoformat(),
        'dias_restantes': license.dias_restantes,
        'estado': license.estado,
        'grace_reset': True
    }), 200
