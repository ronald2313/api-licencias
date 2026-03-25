from datetime import datetime
from app import db
import hashlib
import hmac
import os


class License(db.Model):
    """Licencias del sistema - Versión Segura"""

    __tablename__ = "licenses"

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(50), unique=True, nullable=False, index=True)

    # Relación con cliente
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)

    # Hardware vinculado (hasheado para privacidad)
    hardware_id_hash = db.Column(db.String(64), nullable=True)
    hardware_salt = db.Column(db.String(32), nullable=True)

    # Fechas
    fecha_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_expiracion = db.Column(db.DateTime, nullable=False)

    # Estado: activa, vencida, suspendida, por_vencer, gracia
    estado = db.Column(db.String(20), default="activa", nullable=False)

    # Control de gracia
    grace_used = db.Column(db.Boolean, default=False)
    grace_started_at = db.Column(db.DateTime, nullable=True)
    grace_hours_allowed = db.Column(db.Integer, default=24)

    # Control offline
    last_offline_check = db.Column(db.DateTime, nullable=True)
    offline_days_used = db.Column(db.Integer, default=0)
    max_offline_days = db.Column(db.Integer, default=1)

    # Seguridad
    activation_count = db.Column(db.Integer, default=0)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_reason = db.Column(db.String(100), nullable=True)

    # Firma digital
    signature = db.Column(db.String(128), nullable=True)

    # Última validación
    last_validation = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relaciones
    validation_logs = db.relationship(
        "ValidationLog",
        backref="license",
        lazy=True,
        cascade="all, delete-orphan"
    )
    renewals = db.relationship(
        "Renewal",
        backref="license",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<License {self.license_key} ({self.estado})>"

    @staticmethod
    def _hash_hardware(hardware_id, salt=None):
        """Hashea hardware_id de forma segura."""
        if not salt:
            salt = os.urandom(16).hex()
        hash_value = hashlib.sha256(f"{hardware_id}{salt}".encode()).hexdigest()
        return hash_value, salt

    def set_hardware_id(self, hardware_id):
        """Guardar hardware_id hasheado."""
        hash_value, salt = self._hash_hardware(hardware_id)
        self.hardware_id_hash = hash_value
        self.hardware_salt = salt

    def verify_hardware_id(self, hardware_id):
        """Verificar si el hardware_id coincide."""
        if not self.hardware_id_hash:
            return True
        hash_value, _ = self._hash_hardware(hardware_id, self.hardware_salt)
        return hmac.compare_digest(hash_value, self.hardware_id_hash)

    @property
    def dias_restantes(self):
        """Calcular días restantes hasta expiración."""
        hoy = datetime.utcnow().date()
        expiracion = self.fecha_expiracion.date() if self.fecha_expiracion else hoy
        return (expiracion - hoy).days

    @property
    def grace_hours_remaining(self):
        """Horas restantes del período de gracia."""
        if not self.grace_used or not self.grace_started_at:
            return self.grace_hours_allowed

        elapsed = (datetime.utcnow() - self.grace_started_at).total_seconds() / 3600
        remaining = self.grace_hours_allowed - elapsed
        return max(0, int(remaining))

    @property
    def esta_en_periodo_gracia(self):
        """Indica si la licencia está dentro del período de gracia."""
        if not self.grace_used or not self.grace_started_at:
            return False
        return self.grace_hours_remaining > 0

    @property
    def esta_activa(self):
        """Verificar si la licencia está activa."""
        if self.revoked_at:
            return False
        return self.estado == "activa" and self.dias_restantes > 0

    @property
    def esta_vencida(self):
        """Verificar si la licencia está vencida."""
        return self.dias_restantes <= 0 and not self.esta_en_periodo_gracia

    @property
    def esta_por_vencer(self):
        """Verificar si vence en 3 días o menos."""
        return 0 < self.dias_restantes <= 3

    def actualizar_estado(self):
        """Actualizar estado basado en fecha de expiración."""
        if self.revoked_at:
            self.estado = "suspendida"
        elif self.esta_en_periodo_gracia:
            self.estado = "gracia"
        elif self.dias_restantes <= 0:
            self.estado = "vencida"
        elif self.dias_restantes <= 3:
            self.estado = "por_vencer"
        else:
            self.estado = "activa"

    def start_grace_period(self):
        """Iniciar período de gracia."""
        if not self.grace_used:
            self.grace_used = True
            self.grace_started_at = datetime.utcnow()
            return True
        return False

    def generate_signature(self, secret_key):
        """Generar firma digital de la licencia."""
        data = f"{self.license_key}:{self.hardware_id_hash}:{self.fecha_expiracion.isoformat()}"
        self.signature = hmac.new(
            secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

    def verify_signature(self, secret_key):
        """Verificar firma digital."""
        if not self.signature:
            return False

        data = f"{self.license_key}:{self.hardware_id_hash}:{self.fecha_expiracion.isoformat()}"
        expected = hmac.new(
            secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, self.signature)

    def to_dict(self, include_customer=False, include_sensitive=False):
        """Serializar licencia."""
        data = {
            "id": self.id,
            "license_key": self.license_key,
            "customer_id": self.customer_id,
            "fecha_inicio": self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            "fecha_expiracion": self.fecha_expiracion.isoformat() if self.fecha_expiracion else None,
            "estado": self.estado,
            "dias_restantes": self.dias_restantes,
            "grace_used": self.grace_used,
            "grace_hours_remaining": self.grace_hours_remaining if self.esta_en_periodo_gracia else None,
            "esta_en_periodo_gracia": self.esta_en_periodo_gracia,
            "esta_activa": self.esta_activa,
            "esta_vencida": self.esta_vencida,
            "esta_por_vencer": self.esta_por_vencer,
            "activation_count": self.activation_count,
            "last_validation": self.last_validation.isoformat() if self.last_validation else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_sensitive:
            data["revoked_at"] = self.revoked_at.isoformat() if self.revoked_at else None
            data["revoked_reason"] = self.revoked_reason
            data["offline_days_used"] = self.offline_days_used
            data["max_offline_days"] = self.max_offline_days
            data["hardware_id_hash"] = self.hardware_id_hash

        if include_customer:
            customer = getattr(self, "customer", None)
            if customer and hasattr(customer, "to_dict"):
                data["customer"] = customer.to_dict()

        return data

    def to_signed_response(self, secret_key):
        """Generar respuesta firmada para el cliente."""
        data = self.to_dict()
        signature = hmac.new(
            secret_key.encode(),
            str(data).encode(),
            hashlib.sha256
        ).hexdigest()

        return {
            "data": data,
            "signature": signature,
            "timestamp": datetime.utcnow().isoformat(),
        }