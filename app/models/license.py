from datetime import datetime, timedelta
from app import db


class License(db.Model):
    """Licencias del sistema"""

    __tablename__ = 'licenses'

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Relación con cliente
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)

    # Hardware vinculado (puede ser null hasta activar)
    hardware_id = db.Column(db.String(64), nullable=True)

    # Fechas
    fecha_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_expiracion = db.Column(db.DateTime, nullable=False)

    # Estado: activa, vencida, suspendida, por_vencer
    estado = db.Column(db.String(20), default='activa', nullable=False)

    # Control de gracia (para saber si ya usó su período)
    grace_used = db.Column(db.Boolean, default=False)

    # Última validación recibida
    last_validation = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    validation_logs = db.relationship('ValidationLog', backref='license', lazy=True, cascade='all, delete-orphan')
    renewals = db.relationship('Renewal', backref='license', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<License {self.license_key} ({self.estado})>'

    @property
    def dias_restantes(self):
        """Calcular días restantes hasta expiración"""
        hoy = datetime.utcnow().date()
        expiracion = self.fecha_expiracion.date() if self.fecha_expiracion else hoy
        return (expiracion - hoy).days

    @property
    def esta_activa(self):
        """Verificar si la licencia está activa"""
        return self.estado == 'activa' and self.dias_restantes > 0

    @property
    def esta_vencida(self):
        """Verificar si la licencia está vencida"""
        return self.dias_restantes <= 0

    @property
    def esta_por_vencer(self):
        """Verificar si vence en 3 días o menos"""
        return 0 < self.dias_restantes <= 3

    def actualizar_estado(self):
        """Actualizar estado basado en fecha de expiración"""
        if self.dias_restantes <= 0:
            if self.estado != 'vencida':
                self.estado = 'vencida'
        elif self.dias_restantes <= 3:
            if self.estado != 'por_vencer':
                self.estado = 'por_vencer'
        elif self.estado not in ['suspendida']:
            self.estado = 'activa'

    def to_dict(self, include_customer=False):
        data = {
            'id': self.id,
            'license_key': self.license_key,
            'hardware_id': self.hardware_id,
            'fecha_inicio': self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            'fecha_expiracion': self.fecha_expiracion.isoformat() if self.fecha_expiracion else None,
            'estado': self.estado,
            'dias_restantes': self.dias_restantes,
            'grace_used': self.grace_used,
            'last_validation': self.last_validation.isoformat() if self.last_validation else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

        if include_customer and self.customer:
            data['customer'] = self.customer.to_dict()

        return data
