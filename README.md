# API de Licencias - Sistema de Facturación

API central para validación de licencias del sistema de facturación local.

## 🚀 Deploy en Render

### Paso 1: Crear cuenta y servicio

1. Crear cuenta en [Render](https://render.com)
2. Crear nuevo **Web Service**
3. Conectar con tu repositorio Git

### Paso 2: Configurar variables de entorno

Render usará automáticamente el archivo `render.yaml`, pero puedes configurar manualmente:

```bash
FLASK_ENV=production
SECRET_KEY=tu-clave-secreta-aqui
DATABASE_URL=postgresql://... (Render lo genera automáticamente)
GRACE_PERIOD_HOURS=24
```

### Paso 3: Crear base de datos

En el dashboard de Render:
1. Crear **PostgreSQL** → New PostgreSQL
2. Nombre: `licencias-db`
3. Plan: Free (o Starter para producción)

### Paso 4: Deploy automático

Cada push a la rama principal desplegará automáticamente.

URL de la API: `https://api-licencias-xxxx.onrender.com`

---

## 🛠️ Desarrollo Local

### Requisitos

- Python 3.11+
- PostgreSQL (local o Docker)

### Instalación

```bash
# Clonar repositorio
cd api-licencias

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate    # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones
```

### Configurar base de datos local

```bash
# Crear base de datos PostgreSQL
createdb licencias_db

# O con Docker
docker run -d -p 5432:5432 -e POSTGRES_DB=licencias_db -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres postgres:15
```

### Ejecutar migraciones

```bash
flask db init      # Solo primera vez
flask db migrate   # Crear migración
flask db upgrade   # Aplicar migración
```

### Ejecutar servidor

```bash
# Modo desarrollo
python run.py

# O con Flask
flask run --host=0.0.0.0 --port=5001

# Gunicorn (producción local)
gunicorn -w 4 -b 0.0.0.0:5001 "app:create_app()"
```

---

## 📋 Comandos útiles

```bash
# Crear base de datos
flask create-db

# Crear datos de prueba
flask seed-db

# Shell interactivo
flask shell
```

---

## 🔌 Endpoints API

### Health Check

```bash
GET /health
GET /
```

### Activación

```bash
POST /api/v1/activate
Content-Type: application/json

{
  "license_key": "LIC-TEST-001",
  "hardware_id": "a7f3c8e9...",
  "version": "1.0.0"
}
```

### Validación

```bash
POST /api/v1/validate
Content-Type: application/json

{
  "license_key": "LIC-TEST-001",
  "hardware_id": "a7f3c8e9...",
  "version": "1.0.0"
}
```

### Renovación

```bash
POST /api/v1/renew
Content-Type: application/json

{
  "license_key": "LIC-TEST-001",
  "hardware_id": "a7f3c8e9...",
  "periodo_meses": 12
}
```

### Configuración del negocio

```bash
GET /api/v1/business-config
Authorization: Bearer LIC-TEST-001
# O
GET /api/v1/business-config?license_key=LIC-TEST-001
```

---

## 🗄️ Modelos de Datos

### Customer (Clientes)
- id, nombre, email, telefono, direccion
- Relación: licenses, business_config

### License (Licencias)
- id, license_key, customer_id, hardware_id
- fecha_inicio, fecha_expiracion
- estado (activa, vencida, suspendida, por_vencer)
- grace_used, last_validation

### BusinessConfig (Configuración del negocio)
- id, customer_id
- nombre_negocio, telefono, direccion, rnc_cedula
- email, logo_url, mensaje_factura

### ValidationLog (Logs)
- id, license_id, hardware_id, ip_cliente
- resultado, mensaje, version_cliente, fecha

### Renewal (Renovaciones)
- id, license_id, fecha_renovacion
- nueva_fecha_expiracion, periodo_meses, monto

---

## 🔒 Seguridad

- **HMAC**: Firma de datos críticos
- **Hardware ID**: Vinculación a máquina física
- **Rollback detection**: Detección de cambio de fecha
- **HTTPS**: Comunicación encriptada (Render)
- **Grace period**: 24 horas único por licencia

---

## 📊 Estructura del proyecto

```
api-licencias/
├── app/
│   ├── __init__.py          # Factory app
│   ├── models/              # Modelos SQLAlchemy
│   │   ├── __init__.py
│   │   ├── customer.py
│   │   ├── license.py
│   │   ├── business_config.py
│   │   ├── validation_log.py
│   │   └── renewal.py
│   └── routes/              # Blueprints
│       ├── __init__.py
│       ├── licenses.py      # activate, validate, renew
│       └── config.py        # business-config
├── config/
│   └── __init__.py          # Configuraciones Flask
├── migrations/              # Alembic (auto-generado)
├── .env.example             # Variables de entorno
├── .gitignore
├── render.yaml              # Config Render
├── requirements.txt
├── run.py                   # Script ejecución local
└── README.md
```

---

## 📝 Notas

- **Sistema local (.exe)** usará SQLite, **NO** esta base de datos
- Esta API solo gestiona licencias y configuración remota
- El sistema local sincroniza `business-config` cuando tiene internet

---

## 🆘 Soporte

Para problemas o preguntas, revisar logs en Render Dashboard → Logs.
