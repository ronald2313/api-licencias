"""
Rutas del Panel Administrativo Web
Gestión de licencias, clientes y configuración via HTML templates
"""
from datetime import datetime, timedelta
from functools import wraps
import os

from flask import (
    render_template, request, redirect, url_for, flash,
    session, current_app
)
from sqlalchemy import func, desc
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import (
    License, Customer, BusinessConfig,
    ValidationLog, Renewal
)
from . import admin_bp


def admin_required(f):
    """Decorador para proteger rutas admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            flash('Por favor, inicie sesión como administrador', 'warning')
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function


def verify_admin_credentials(username, password):
    """Verificar credenciales de admin desde variables de entorno"""
    expected_user = os.environ.get('ADMIN_USERNAME', 'admin')
    expected_pass = os.environ.get('ADMIN_PASSWORD')
    if not expected_pass:
        # Fallback para desarrollo - NO USAR EN PRODUCCION
        expected_pass = 'admin123'
    return username == expected_user and password == expected_pass


# ============================================
# AUTH
# ============================================

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login de administrador"""
    if 'admin_logged_in' in session:
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Usuario y contraseña son requeridos', 'error')
            return render_template('admin/login.html')

        if verify_admin_credentials(username, password):
            session['admin_logged_in'] = True
            session['admin_user'] = username
            flash('Bienvenido al Panel de Administración', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Credenciales incorrectas', 'error')

    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    """Cerrar sesión de admin"""
    session.pop('admin_logged_in', None)
    session.pop('admin_user', None)
    flash('Sesión cerrada', 'info')
    return redirect(url_for('admin.login'))


# ============================================
# DASHBOARD
# ============================================

@admin_bp.route('/')
@admin_required
def dashboard():
    """Dashboard principal con estadísticas"""
    total_licenses = License.query.count()
    active_licenses = License.query.filter(
        License.estado == 'activa',
        License.fecha_expiracion > datetime.utcnow()
    ).count()
    expired_licenses = License.query.filter(
        License.fecha_expiracion < datetime.utcnow()
    ).count()
    suspended_licenses = License.query.filter(
        License.estado == 'suspendida'
    ).count()
    grace_licenses = License.query.filter(
        License.estado == 'gracia'
    ).count()

    total_customers = Customer.query.count()

    last_24h = datetime.utcnow() - timedelta(hours=24)
    recent_validations = ValidationLog.query.filter(
        ValidationLog.fecha >= last_24h
    ).count()

    recent_renewals = Renewal.query.filter(
        Renewal.created_at >= last_24h
    ).count()

    next_7_days = datetime.utcnow() + timedelta(days=7)
    expiring_soon = License.query.filter(
        License.fecha_expiracion <= next_7_days,
        License.fecha_expiracion > datetime.utcnow(),
        License.estado != 'suspendida'
    ).order_by(License.fecha_expiracion).limit(5).all()

    recent_validation_logs = ValidationLog.query.order_by(
        desc(ValidationLog.fecha)
    ).limit(10).all()

    recent_renewal_logs = Renewal.query.order_by(
        desc(Renewal.created_at)
    ).limit(10).all()

    counts = {
        'total': total_licenses,
        'activa': active_licenses,
        'vencida': expired_licenses,
        'suspendida': suspended_licenses,
        'por_vencer': grace_licenses,
        'gracia': grace_licenses
    }

    return render_template('admin/dashboard.html',
                           total_licenses=total_licenses,
                           active_licenses=active_licenses,
                           expired_licenses=expired_licenses,
                           suspended_licenses=suspended_licenses,
                           grace_licenses=grace_licenses,
                           total_customers=total_customers,
                           recent_validations=recent_validations,
                           recent_renewals=recent_renewals,
                           expiring_soon=expiring_soon,
                           recent_validation_logs=recent_validation_logs,
                           recent_renewal_logs=recent_renewal_logs,
                           counts=counts)


# ============================================
# GESTIÓN DE LICENCIAS
# ============================================

@admin_bp.route('/licenses')
@admin_required
def licenses_list():
    """Listar todas las licencias con búsqueda y filtros"""
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20

    query = License.query.join(Customer)

    if search:
        query = query.filter(
            db.or_(
                License.license_key.ilike(f'%{search}%'),
                Customer.nombre.ilike(f'%{search}%'),
                Customer.email.ilike(f'%{search}%')
            )
        )

    if status:
        query = query.filter(License.estado == status)

    query = query.order_by(License.fecha_expiracion)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    licenses = pagination.items

    counts = {
        'total': License.query.count(),
        'activa': License.query.filter_by(estado='activa').count(),
        'vencida': License.query.filter_by(estado='vencida').count(),
        'suspendida': License.query.filter_by(estado='suspendida').count(),
        'por_vencer': License.query.filter_by(estado='por_vencer').count(),
        'gracia': License.query.filter_by(estado='gracia').count()
    }

    return render_template('admin/licenses.html',
                           licenses=licenses,
                           pagination=pagination,
                           search=search,
                           status=status,
                           counts=counts)


@admin_bp.route('/licenses/<int:license_id>')
@admin_required
def license_detail(license_id):
    """Ver detalle de una licencia"""
    license_obj = License.query.get_or_404(license_id)

    validation_history = ValidationLog.query.filter_by(
        license_id=license_id
    ).order_by(desc(ValidationLog.fecha)).limit(50).all()

    renewal_history = Renewal.query.filter_by(
        license_id=license_id
    ).order_by(desc(Renewal.created_at)).all()

    return render_template('admin/license_detail.html',
                           license=license_obj,
                           validation_history=validation_history,
                           renewal_history=renewal_history)


@admin_bp.route('/licenses/new', methods=['GET', 'POST'])
@admin_required
def license_new():
    """Crear nueva licencia"""
    customers = Customer.query.order_by(Customer.nombre).all()

    if request.method == 'POST':
        license_key = request.form.get('license_key', '').strip().upper()
        customer_id = request.form.get('customer_id', type=int)
        periodo_meses = request.form.get('periodo_meses', 12, type=int)

        if not license_key:
            flash('La clave de licencia es requerida', 'error')
            return render_template('admin/license_form.html',
                                   customers=customers)

        if not customer_id:
            flash('Debe seleccionar un cliente', 'error')
            return render_template('admin/license_form.html',
                                   customers=customers)

        existing = License.query.filter_by(license_key=license_key).first()
        if existing:
            flash('Ya existe una licencia con esa clave', 'error')
            return render_template('admin/license_form.html',
                                   customers=customers)

        try:
            hoy = datetime.utcnow()
            fecha_exp = hoy + timedelta(days=30 * periodo_meses)

            license_obj = License(
                license_key=license_key,
                customer_id=customer_id,
                fecha_inicio=hoy,
                fecha_expiracion=fecha_exp,
                estado='activa'
            )

            db.session.add(license_obj)

            existing_config = BusinessConfig.query.filter_by(
                customer_id=customer_id
            ).first()
            if not existing_config:
                customer = Customer.query.get(customer_id)
                config = BusinessConfig(
                    customer_id=customer_id,
                    nombre_negocio=customer.nombre or 'Mi Negocio',
                    email=customer.email
                )
                db.session.add(config)

            db.session.commit()

            flash(f'Licencia {license_key} creada exitosamente', 'success')
            return redirect(url_for('admin.license_detail',
                                   license_id=license_obj.id))

        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error al crear licencia: {str(e)}', 'error')

    return render_template('admin/license_form.html',
                           customers=customers)


@admin_bp.route('/licenses/<int:license_id>/renew', methods=['POST'])
@admin_required
def license_renew(license_id):
    """Renovar una licencia existente"""
    license_obj = License.query.get_or_404(license_id)
    periodo_meses = request.form.get('periodo_meses', 12, type=int)

    try:
        hoy = datetime.utcnow()
        nueva_fecha = hoy + timedelta(days=30 * periodo_meses)
        fecha_anterior = license_obj.fecha_expiracion

        license_obj.fecha_expiracion = nueva_fecha
        license_obj.estado = 'activa'
        license_obj.grace_used = False
        license_obj.grace_started_at = None
        license_obj.offline_days_used = 0
        license_obj.last_validation = hoy

        renewal = Renewal(
            license_id=license_id,
            nueva_fecha_expiracion=nueva_fecha,
            periodo_meses=periodo_meses,
            estado='completada',
            notas=f'Renovación desde panel admin. Fecha anterior: {fecha_anterior}'
        )
        db.session.add(renewal)
        db.session.commit()

        flash(f'Licencia renovada exitosamente. Nueva expiración: {nueva_fecha.strftime("%d/%m/%Y")}', 'success')

    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Error al renovar: {str(e)}', 'error')

    return redirect(url_for('admin.license_detail', license_id=license_id))


@admin_bp.route('/licenses/<int:license_id>/suspend', methods=['POST'])
@admin_required
def license_suspend(license_id):
    """Suspender/reactivar una licencia"""
    license_obj = License.query.get_or_404(license_id)
    action = request.form.get('action')
    reason = request.form.get('reason', '')

    try:
        if action == 'suspend':
            license_obj.estado = 'suspendida'
            license_obj.revoked_at = datetime.utcnow()
            license_obj.revoked_reason = reason or 'Suspendida desde panel admin'
            flash('Licencia suspendida', 'warning')
        elif action == 'reactivate':
            license_obj.estado = 'activa'
            license_obj.revoked_at = None
            license_obj.revoked_reason = None
            flash('Licencia reactivada', 'success')

        db.session.commit()

    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Error: {str(e)}', 'error')

    return redirect(url_for('admin.license_detail', license_id=license_id))


# ============================================
# GESTIÓN DE CLIENTES
# ============================================

@admin_bp.route('/customers')
@admin_required
def customers_list():
    """Listar todos los clientes"""
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    query = Customer.query

    if search:
        query = query.filter(
            db.or_(
                Customer.nombre.ilike(f'%{search}%'),
                Customer.email.ilike(f'%{search}%')
            )
        )

    pagination = query.order_by(Customer.nombre).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template('admin/customers.html',
                           customers=pagination.items,
                           pagination=pagination,
                           search=search)


@admin_bp.route('/customers/<int:customer_id>')
@admin_required
def customer_detail(customer_id):
    """Ver detalle de un cliente"""
    customer = Customer.query.get_or_404(customer_id)
    licenses = License.query.filter_by(customer_id=customer_id).all()
    business_config = BusinessConfig.query.filter_by(
        customer_id=customer_id
    ).first()

    return render_template('admin/customer_detail.html',
                           customer=customer,
                           licenses=licenses,
                           config=business_config)


@admin_bp.route('/customers/new', methods=['GET', 'POST'])
@admin_required
def customer_new():
    """Crear nuevo cliente"""
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        email = request.form.get('email', '').strip()
        telefono = request.form.get('telefono', '').strip()
        direccion = request.form.get('direccion', '').strip()

        if not nombre or not email:
            flash('Nombre y email son requeridos', 'error')
            return render_template('admin/customer_form.html')

        existing = Customer.query.filter_by(email=email).first()
        if existing:
            flash('Ya existe un cliente con ese email', 'error')
            return render_template('admin/customer_form.html')

        try:
            customer = Customer(
                nombre=nombre,
                email=email,
                telefono=telefono,
                direccion=direccion
            )
            db.session.add(customer)
            db.session.commit()

            config = BusinessConfig(
                customer_id=customer.id,
                nombre_negocio=nombre,
                email=email,
                telefono=telefono,
                direccion=direccion
            )
            db.session.add(config)
            db.session.commit()

            flash('Cliente creado exitosamente', 'success')
            return redirect(url_for('admin.customer_detail',
                                   customer_id=customer.id))

        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')

    return render_template('admin/customer_form.html')


# ============================================
# BUSINESS CONFIG
# ============================================

@admin_bp.route('/business-config/<int:customer_id>', methods=['GET', 'POST'])
@admin_required
def business_config_edit(customer_id):
    """Editar configuración del negocio"""
    config = BusinessConfig.query.filter_by(customer_id=customer_id).first()
    customer = Customer.query.get_or_404(customer_id)

    if not config:
        config = BusinessConfig(
            customer_id=customer_id,
            nombre_negocio=customer.nombre or 'Mi Negocio',
            email=customer.email
        )
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        config.nombre_negocio = request.form.get('nombre_negocio', '').strip()
        config.telefono = request.form.get('telefono', '').strip()
        config.direccion = request.form.get('direccion', '').strip()
        config.rnc_cedula = request.form.get('rnc_cedula', '').strip()
        config.email = request.form.get('email', '').strip()
        config.mensaje_factura = request.form.get('mensaje_factura', '').strip()
        config.logo_url = request.form.get('logo_url', '').strip()

        try:
            db.session.commit()
            flash('Configuración actualizada exitosamente', 'success')
            return redirect(url_for('admin.customer_detail',
                                   customer_id=customer_id))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')

    return render_template('admin/business_config_form.html',
                           config=config,
                           customer=customer)


# ============================================
# HISTORIAL
# ============================================

@admin_bp.route('/history/validations')
@admin_required
def history_validations():
    """Ver historial de validaciones"""
    page = request.args.get('page', 1, type=int)
    license_id = request.args.get('license_id', type=int)

    query = ValidationLog.query.join(License).join(Customer)

    if license_id:
        query = query.filter(ValidationLog.license_id == license_id)

    pagination = query.order_by(desc(ValidationLog.fecha)).paginate(
        page=page, per_page=50, error_out=False
    )

    return render_template('admin/history_validations.html',
                           logs=pagination.items,
                           pagination=pagination,
                           license_id=license_id)


@admin_bp.route('/history/renewals')
@admin_required
def history_renewals():
    """Ver historial de renovaciones"""
    page = request.args.get('page', 1, type=int)

    query = Renewal.query.join(License).join(Customer)

    pagination = query.order_by(desc(Renewal.created_at)).paginate(
        page=page, per_page=50, error_out=False
    )

    return render_template('admin/history_renewals.html',
                           renewals=pagination.items,
                           pagination=pagination)
