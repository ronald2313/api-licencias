-- Migración: Mejorar seguridad del sistema de licencias
-- Ejecutar en PostgreSQL antes de desplegar

-- Agregar columnas de seguridad a licenses
ALTER TABLE licenses
    ADD COLUMN IF NOT EXISTS hardware_id_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS hardware_salt VARCHAR(32),
    ADD COLUMN IF NOT EXISTS grace_started_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS grace_hours_allowed INTEGER DEFAULT 24,
    ADD COLUMN IF NOT EXISTS last_offline_check TIMESTAMP,
    ADD COLUMN IF NOT EXISTS offline_days_used INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_offline_days INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS activation_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS revoked_reason VARCHAR(100),
    ADD COLUMN IF NOT EXISTS signature VARCHAR(128);

-- Migrar datos existentes
-- NOTA: Las licencias existentes con hardware_id necesitarán re-activación
UPDATE licenses
SET activation_count = CASE WHEN hardware_id IS NOT NULL THEN 1 ELSE 0 END;

-- Crear índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_licenses_revoked_at ON licenses(revoked_at);
CREATE INDEX IF NOT EXISTS idx_licenses_hardware_hash ON licenses(hardware_id_hash);

-- Comentarios
COMMENT ON COLUMN licenses.hardware_id_hash IS 'SHA256 del hardware_id + salt';
COMMENT ON COLUMN licenses.grace_started_at IS 'Cuándo inició el período de gracia';
COMMENT ON COLUMN licenses.revoked_at IS 'Timestamp de revocación (NULL si activa)';
