from datetime import datetime
from app import db


class Customer(db.Model):
    """Clientes/Tiendas que tienen licencias"""

    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    telefono = db.Column(db.String(20), nullable=True)
    direccion = db.Column(db.String(255), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relaciones
    licenses = db.relationship('License', backref='customer', lazy=True, cascade='all, delete-orphan')
    business_config = db.relationship('BusinessConfig', backref='customer', lazy=True, uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Customer {self.nombre} ({self.email})>'

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'email': self.email,
            'telefono': self.telefono,
            'direccion': self.direccion,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
