from datetime import datetime
from app import db


class ValidationLog(db.Model):
    """Logs de validaciones de licencias (auditoría)"""

    __tablename__ = 'validation_logs'

    id = db.Column(db.Integer, primary_key=True)

    # Relación con licencia
    license_id = db.Column(db.Integer, db.ForeignKey('licenses.id'), nullable=False)

    # Datos de la validación
    hardware_id = db.Column(db.String(64), nullable=True)
    ip_cliente = db.Column(db.String(45), nullable=True)  # IPv6 puede ser hasta 45 chars

    # Resultado
    resultado = db.Column(db.String(20), nullable=False)  # exito, error, grace, bloqueado
    mensaje = db.Column(db.Text, nullable=True)

    # Metadata de la request
    version_cliente = db.Column(db.String(20), nullable=True)

    # Timestamp
    fecha = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<ValidationLog {self.license_id} - {self.resultado}>'

    def to_dict(self):
        return {
            'id': self.id,
            'license_id': self.license_id,
            'hardware_id': self.hardware_id,
            'ip_cliente': self.ip_cliente,
            'resultado': self.resultado,
            'mensaje': self.mensaje,
            'version_cliente': self.version_cliente,
            'fecha': self.fecha.isoformat() if self.fecha else None
        }
