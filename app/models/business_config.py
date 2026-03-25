from datetime import datetime
from app import db


class BusinessConfig(db.Model):
    """Configuración del negocio (datos que se sincronizan al sistema local)"""

    __tablename__ = 'business_config'

    id = db.Column(db.Integer, primary_key=True)

    # Relación con cliente (única configuración por cliente)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, unique=True)

    # Datos del negocio
    nombre_negocio = db.Column(db.String(100), nullable=False, default='Mi Negocio')
    telefono = db.Column(db.String(20), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)
    rnc_cedula = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    logo_url = db.Column(db.String(500), nullable=True)
    mensaje_factura = db.Column(db.Text, nullable=True, default='Gracias por su preferencia')

    # Control de sincronización
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<BusinessConfig {self.nombre_negocio}>'

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'nombre_negocio': self.nombre_negocio,
            'telefono': self.telefono,
            'direccion': self.direccion,
            'rnc_cedula': self.rnc_cedula,
            'email': self.email,
            'logo_url': self.logo_url,
            'mensaje_factura': self.mensaje_factura,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
