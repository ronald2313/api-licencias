from datetime import datetime
from app import db


class Renewal(db.Model):
    """Historial de renovaciones de licencias"""

    __tablename__ = 'renewals'

    id = db.Column(db.Integer, primary_key=True)

    # Relación con licencia
    license_id = db.Column(db.Integer, db.ForeignKey('licenses.id'), nullable=False)

    # Datos de la renovación
    fecha_renovacion = db.Column(db.DateTime, default=datetime.utcnow)
    nueva_fecha_expiracion = db.Column(db.DateTime, nullable=False)
    periodo_meses = db.Column(db.Integer, nullable=False, default=12)

    # Información de pago (opcional)
    monto = db.Column(db.Numeric(10, 2), nullable=True)
    metodo_pago = db.Column(db.String(50), nullable=True)
    referencia_pago = db.Column(db.String(100), nullable=True)

    # Estado de la renovación
    estado = db.Column(db.String(20), default='completada')  # completada, pendiente, cancelada

    # Notas
    notas = db.Column(db.Text, nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Renewal {self.license_id} - {self.fecha_renovacion}>'

    def to_dict(self):
        return {
            'id': self.id,
            'license_id': self.license_id,
            'fecha_renovacion': self.fecha_renovacion.isoformat() if self.fecha_renovacion else None,
            'nueva_fecha_expiracion': self.nueva_fecha_expiracion.isoformat() if self.nueva_fecha_expiracion else None,
            'periodo_meses': self.periodo_meses,
            'monto': str(self.monto) if self.monto else None,
            'metodo_pago': self.metodo_pago,
            'referencia_pago': self.referencia_pago,
            'estado': self.estado,
            'notas': self.notas,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
