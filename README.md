<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/AWS_S3-Storage-FF9900?style=flat-square&logo=amazons3&logoColor=white" />
</p>

# 🧾 Quipux — Motor de Facturación Electrónica

**Motor backend del sistema inteligente de facturación electrónica para Colombia.** Automatiza la recepción, validación normativa DIAN, almacenamiento y trazabilidad completa de facturas electrónicas de proveedores.

> **¿Qué hace este sistema en palabras simples?**  
> Recibe facturas de proveedores por correo electrónico, las valida automáticamente contra las 18 reglas exigidas por la DIAN, almacena los archivos de forma segura en la nube y notifica si hay problemas — todo sin intervención humana.

---

## 📋 Tabla de Contenidos

- [Características Principales](#-características-principales)
- [Arquitectura](#-arquitectura)
- [Requisitos Previos](#-requisitos-previos)
- [Instalación Rápida](#-instalación-rápida)
- [Configuración](#-configuración)
- [Ejecución](#-ejecución)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [API — Endpoints](#-api--endpoints)
- [Pipeline de Validación](#-pipeline-de-validación)
- [Base de Datos](#-base-de-datos)
- [Despliegue en Producción](#-despliegue-en-producción)
- [Scripts Utilitarios](#-scripts-utilitarios)
- [Testing](#-testing)
- [Glosario](#-glosario)

---

## ✨ Características Principales

| Funcionalidad | Descripción |
|---|---|
| 📬 **Ingesta automática de correo** | Listener IMAP que detecta facturas nuevas en la bandeja de entrada y las procesa automáticamente. |
| ✅ **18 validaciones DIAN** | Cada factura se valida contra las 18 reglas de la normativa colombiana (CUFE, firma digital, impuestos, numeración, etc.). |
| 🔒 **Escaneo antivirus** | ClamAV integrado para detectar malware disfrazado de XML/PDF antes de procesar cualquier archivo. |
| ☁️ **Almacenamiento S3** | Los archivos (XML, PDF, ZIP) se almacenan de forma segura en Amazon S3 con políticas de ciclo de vida. |
| 📊 **Dashboard analítico** | API de dashboard con KPIs en tiempo real, tendencias, métricas por proveedor, formas de pago, impuestos y eventos DIAN. |
| 🤖 **Chatbot de consulta** | Endpoint de chat con LLM para responder preguntas sobre el estado de facturas en lenguaje natural. |
| 🔔 **Sistema de alertas** | Detección automática de inconsistencias, facturas sin eventos DIAN, y facturas próximas a vencer. |
| 📋 **Eventos DIAN** | Listener independiente que monitorea la bandeja de notificaciones DIAN y asocia acuses, aceptaciones y rechazos. |
| 👁️ **Verificación gráfica** | Comparación automatizada entre el XML y el PDF de la factura usando visión por computadora (PyMuPDF). |
| 📤 **Exportación Excel** | Generación de reportes Excel (.xlsx) con filtros avanzados para el equipo contable. |
| 🔐 **Autenticación JWT** | Control de acceso con tokens JWT, gestión de usuarios y roles. |
| ⚡ **Cola de trabajo async** | Workers que procesan facturas en paralelo con reintentos automáticos y backoff exponencial. |

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                        INFRAESTRUCTURA                          │
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Email      │    │   Email      │    │   Webhook    │      │
│  │  Listener    │    │  DIAN Events │    │   Gmail      │      │
│  │  (IMAP)      │    │  Listener    │    │   Trigger    │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │               │
│         ▼                   ▼                   ▼               │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              Cola de Trabajo (DB-backed)             │       │
│  └───────────────────────┬─────────────────────────────┘       │
│                          │                                      │
│         ┌────────────────┼────────────────┐                    │
│         ▼                ▼                ▼                    │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐              │
│  │ Worker 1 │     │ Worker 2 │     │ Worker N │              │
│  └──────┬───┘     └──────┬───┘     └──────┬───┘              │
│         │                │                │                    │
│         └────────────────┼────────────────┘                    │
│                          ▼                                      │
│  ┌──────────────────────────────────────────────┐              │
│  │          Pipeline de Validación (18 reglas)   │              │
│  │  Antivirus → XML → Firma → CUFE → Impuestos  │              │
│  │  → Numeración → Fechas → Valor → QR → ...    │              │
│  └──────────────────────┬───────────────────────┘              │
│                         │                                       │
│              ┌──────────┼──────────┐                           │
│              ▼          ▼          ▼                           │
│         ┌────────┐ ┌────────┐ ┌────────┐                      │
│         │  S3    │ │ Postgres│ │ Alertas│                      │
│         │ (XML,  │ │  (Data) │ │(Correo)│                      │
│         │  PDF)  │ │         │ │        │                      │
│         └────────┘ └────────┘ └────────┘                      │
│                         │                                       │
│                         ▼                                       │
│              ┌──────────────────┐                              │
│              │    FastAPI        │                              │
│              │   (REST API)     │                              │
│              │  Puerto 8888     │                              │
│              └──────────────────┘                              │
│                         │                                       │
│                         ▼                                       │
│              ┌──────────────────┐                              │
│              │   Frontend SPA   │                              │
│              │   (quipuxai)     │                              │
│              └──────────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📦 Requisitos Previos

### Para desarrollo local

- **Python** 3.11+ (recomendado 3.12)
- **PostgreSQL** 15+ (se levanta con Docker)
- **Docker** y **Docker Compose** v2

### Para producción (VPS)

- **Docker** y **Docker Compose** v2
- Un dominio con DNS apuntando al VPS
- Credenciales de correo electrónico (IMAP habilitado)
- Bucket de AWS S3 configurado

---

## 🚀 Instalación Rápida

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-org/FacturacionElectronicaQx.git
cd FacturacionElectronicaQx
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales reales
```

### 3. Levantar con Docker (recomendado)

```bash
docker compose up -d
```

Esto levanta automáticamente:
- 🐘 **PostgreSQL** (base de datos)
- 🛡️ **ClamAV** (antivirus)
- ⚡ **API** (FastAPI en puerto 8888)
- 👷 **Workers** (2 réplicas para procesamiento paralelo)
- 📬 **Email Listener** (polling IMAP)
- 📋 **DIAN Events Listener** (eventos DIAN)
- 🌐 **Frontend** (interfaz web en puerto 3000)

### 4. Desarrollo local (sin Docker para la API)

```bash
# Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
# .\\venv\\Scripts\\activate      # Windows

# Instalar dependencias
pip install -r requirements.txt

# Solo levantar la BD y ClamAV con Docker
docker compose up -d database clamav

# Iniciar la API
python main.py
```

---

## ⚙ Configuración

Copia `.env.example` como `.env` y completa los valores:

| Variable | Descripción | Ejemplo |
|---|---|---|
| `SECRET_KEY` | Clave para firmar tokens JWT | `una-clave-larga-y-segura` |
| `POSTGRES_PASSWORD` | Contraseña de la base de datos | `mi_password_seguro` |
| `EMAIL_USER` | Correo para ingesta de facturas | `facturas@empresa.com` |
| `EMAIL_PASSWORD` | App password del correo | `xxxx xxxx xxxx xxxx` |
| `EMAIL_EVENTS_USER` | Correo para eventos DIAN | `dian@empresa.com` |
| `EMAIL_EVENTS_PASSWORD` | App password eventos | `xxxx xxxx xxxx xxxx` |
| `WEBHOOK_SECRET` | Secreto del webhook Gmail | `mi_secreto_webhook` |
| `CORS_ORIGINS` | Orígenes del frontend | `https://mi-dominio.com` |
| `LLM_API_KEY` | API key del modelo de chat | `sk-...` |
| `DOMAIN` | Dominio de producción | `facturacion.empresa.com` |

> ⚠️ **Nunca subas el archivo `.env` al repositorio.** Ya está en `.gitignore`.

---

## ▶ Ejecución

| Comando | Descripción |
|---|---|
| `docker compose up -d` | Levantar todos los servicios |
| `docker compose up -d database clamav` | Solo base de datos + antivirus |
| `python main.py` | Iniciar la API localmente |
| `python -m core.python.ingesta.queue_worker` | Iniciar un worker manualmente |
| `python -m core.python.ingesta.email_listener` | Iniciar listener de correo |
| `python -m core.python.ingesta.dian_events.listener` | Iniciar listener DIAN |

La API estará disponible en `http://localhost:8888`.

- 📖 **Swagger UI:** `http://localhost:8888/docs`
- ❤️ **Health check:** `GET /` → `{"status": "online"}`

---

## 📁 Estructura del Proyecto

```
FacturacionElectronicaQx/
├── main.py                          # Punto de entrada de la API
├── config.py                        # Carga de configuración YAML + .env
├── docker-compose.yml               # Orquestación de servicios
├── Dockerfile                       # Imagen Docker de la API
├── modelo_facturacion.sql           # Schema SQL inicial (auto-migración)
├── pyproject.toml                   # Dependencias y configuración del proyecto
│
├── config/                          # Archivos de configuración YAML
│   ├── settings.yaml                # Configuración general
│   └── tool_definitions.yml         # Definiciones de herramientas (chatbot)
│
├── core/python/                     # Lógica de negocio principal
│   ├── auth/                        # Autenticación JWT y gestión de usuarios
│   ├── chat/                        # Chatbot LLM para consultas
│   ├── db/                          # Pool de conexiones PostgreSQL (psycopg)
│   ├── exports/                     # Generación de reportes Excel
│   ├── facturas/                    # Servicio de gestión de facturas
│   ├── ingesta/                     # Pipeline de ingesta
│   │   ├── email_listener.py        # Polling IMAP de facturas
│   │   ├── queue_publisher.py       # Publicador de tareas a la cola
│   │   ├── queue_worker.py          # Worker que procesa facturas
│   │   └── dian_events/             # Listener de eventos DIAN
│   ├── validators/                  # 18 validaciones DIAN
│   │   ├── req_01_denominacion.py   # Denominación del documento
│   │   ├── req_02_vendedor.py       # Datos del vendedor
│   │   ├── ...                      # (req_03 a req_17)
│   │   ├── req_18_proveedor_sw.py   # Proveedor tecnológico
│   │   └── validacion_grafica.py    # Verificación visual PDF vs XML
│   ├── services/                    # Servicios de consulta (dashboard, etc.)
│   ├── schemas/                     # Modelos Pydantic
│   └── verificacion_grafica/        # Motor de verificación visual
│
├── routers/                         # Endpoints de la API
│   ├── auth.py                      # Login, registro, tokens
│   ├── dashboard.py                 # KPIs, gráficos, tendencias
│   ├── facturas.py                  # CRUD de facturas
│   ├── control.py                   # Control de facturas
│   ├── proveedores.py               # Gestión de proveedores
│   ├── validaciones.py              # Reglas de validación
│   ├── rechazos.py                  # Facturas rechazadas
│   ├── logs_router.py               # Logs del sistema
│   ├── chat.py                      # Chat con IA
│   ├── exports.py                   # Exportación Excel
│   ├── ingesta.py                   # Webhook de ingesta
│   └── usuarios.py                  # Gestión de usuarios
│
├── metadata/                        # Constantes y textos del dominio
├── migrations/                      # Migraciones SQL incrementales
├── scripts/                         # Utilidades y seeds
├── input/                           # Queries SQL, credenciales, catálogos
├── tests/                           # Suite de pruebas
└── utils/                           # Utilidades compartidas
```

---

## 🔌 API — Endpoints

Todos los endpoints (excepto `/api/auth` y `/`) requieren un token JWT en el header `Authorization: Bearer <token>`.

### Públicos

| Endpoint | Método | Descripción |
|---|---|---|
| `GET /` | GET | Health check |
| `POST /api/auth/login` | POST | Autenticación y obtención de token |
| `POST /api/auth/register` | POST | Registro de usuario |
| `POST /webhook/gmail` | POST | Webhook de notificación de Gmail |

### Protegidos (requieren JWT)

| Endpoint | Método | Descripción |
|---|---|---|
| `GET /api/dashboard` | GET | Dashboard completo (KPIs, gráficos, tendencias, alertas) |
| `GET /api/facturas` | GET | Listado de facturas con filtros, paginación y estadísticas |
| `GET /api/facturas/{id}` | GET | Detalle de una factura |
| `POST /api/facturas/{id}/rechazar` | POST | Rechazar factura manualmente |
| `GET /api/proveedores` | GET | Listado de proveedores con métricas |
| `GET /api/validaciones` | GET | Reglas de validación con conteos passed/failed |
| `GET /api/rechazos` | GET | Facturas rechazadas con causas frecuentes |
| `GET /api/logs` | GET | Logs del sistema con conteos por nivel |
| `GET /api/logs/trail` | GET | Trazabilidad completa de una factura |
| `GET /api/control` | GET | Control de facturas con eventos DIAN |
| `POST /api/chat` | POST | Consulta al chatbot sobre facturas |
| `GET /api/exports/excel` | GET | Exportación de datos a Excel |
| `GET /api/usuarios` | GET | Lista de usuarios del sistema |

---

## 🔍 Pipeline de Validación

Cada factura pasa por **18 validaciones** alineadas con la normativa de la DIAN:

| # | Validación | Descripción |
|---|---|---|
| 01 | Denominación | Verifica el tipo de documento electrónico (factura, nota crédito, etc.) |
| 02 | Vendedor | Datos del emisor (NIT, razón social, régimen fiscal) |
| 03 | Adquiriente | Datos del receptor de la factura |
| 04 | Numeración | Prefijo, consecutivo y resolución de facturación |
| 05 | Fecha Generación | Fecha de emisión dentro de rango válido |
| 06 | Fecha Validación | Coherencia de fechas de validación DIAN |
| 07 | Validación DIAN | Estado de validación ante la DIAN |
| 08 | Ítems | Líneas de detalle (descripción, cantidad, precio) |
| 09 | Valor | Totales y subtotales coherentes |
| 10 | Forma de Pago | Contado, crédito u otra forma válida |
| 11 | Medio de Pago | Transferencia, efectivo, cheque, etc. |
| 12 | Calidad Tributaria | Responsabilidades fiscales del emisor |
| 13 | Impuestos | IVA, retenciones y otros tributos correctos |
| 14 | Firma Digital | Integridad de la firma XML (XMLDSig + X.509) |
| 15 | CUFE | Código Único de Factura Electrónica válido |
| 16 | QR Code | Presencia y contenido del código QR |
| 17 | Anexo Técnico | Conformidad con el anexo técnico DIAN |
| 18 | Proveedor Software | Datos del proveedor tecnológico autorizado |
| — | Verificación Gráfica | Comparación automatizada XML vs PDF |

---

## 🗄 Base de Datos

### Inicialización automática

Al levantar Docker por primera vez, PostgreSQL ejecuta `modelo_facturacion.sql` que crea todo el esquema dentro de `facturacion.*`.

### Migraciones

Las migraciones incrementales se encuentran en `migrations/`:

| Archivo | Descripción |
|---|---|
| `002_add_motivo_descarte.sql` | Agrega campo de motivo de descarte |
| `003_observacion_text.sql` | Campo de observaciones en texto libre |
| `add_verificacion_grafica_detalle.sql` | Soporte para verificación gráfica |

```bash
# Ejecutar una migración específica
psql -h 127.0.0.1 -p 5433 -U admin -d facturacion -f migrations/002_add_motivo_descarte.sql

# Ejecutar todas las migraciones pendientes
for f in migrations/*.sql; do
  echo "Ejecutando $f..."
  psql -h 127.0.0.1 -p 5433 -U admin -d facturacion -f "$f"
done
```

### Datos de prueba

```bash
# Poblar con datos de ejemplo (⚠️ borra datos existentes)
python scripts/seed.py
```

### Conexión

- **Host:** `localhost`
- **Puerto externo:** `5433` (configurable con `DB_EXTERNAL_PORT`)
- **Base de datos:** `facturacion`
- **Usuario:** Valor de `POSTGRES_USER` en `.env`

---

## 🚢 Despliegue en Producción

### 1. Configurar el VPS

```bash
# Instalar Docker
curl -fsSL https://get.docker.com | sh

# Clonar el repositorio
git clone https://github.com/tu-org/FacturacionElectronicaQx.git
cd FacturacionElectronicaQx
```

### 2. Configurar credenciales

```bash
cp .env.example .env
nano .env  # Completar TODAS las variables

# Colocar credenciales de S3
mkdir -p input/credentials
# Copiar s3_connection.yml y ca_bundle.pem
```

### 3. Levantar

```bash
docker compose up -d --build
```

### 4. Verificar

```bash
# Ver logs de todos los servicios
docker compose logs -f

# Verificar que la API responde
curl https://tu-dominio.com/
```

### Seguridad en producción

- ✅ Usar contraseñas fuertes en `.env` (nunca los valores por defecto)
- ✅ Configurar firewall (UFW) para restringir puertos
- ✅ HTTPS habilitado automáticamente vía nginx-proxy + Let's Encrypt
- ✅ ClamAV escanea todos los archivos antes de procesar

---

## 🛠 Scripts Utilitarios

| Script | Comando | Descripción |
|---|---|---|
| Seed de datos | `python scripts/seed.py` | Poblar BD con datos de ejemplo |
| Truncar todo | `python scripts/truncate_all.py` | Vaciar todas las tablas |
| Verificar schema | `python scripts/check_schema.py` | Validar estructura de la BD |
| Trigger Gmail | `scripts/gmail_trigger.js` | Google Apps Script para webhook |
| Setup S3 Lifecycle | `python scripts/setup_s3_lifecycle.py` | Configurar políticas S3 |
| Setup DIAN Trigger | `python scripts/setup_dian_trigger.py` | Configurar listener DIAN |
| Scheduler Alertas | `python scripts/alertas_dian_scheduler.py` | Programar alertas DIAN |
| Verificar conexión DB | `python check_db.py` | Probar conexión a PostgreSQL |

---

## 🧪 Testing

```bash
# Instalar dependencias de testing
pip install -e ".[test]"

# Ejecutar tests con cobertura
pytest

# Solo tests de un módulo
pytest tests/test_validators.py -v
```

La configuración de pytest se encuentra en `pyproject.toml` y genera reportes de cobertura de `core/` y `utils/`.

---

## 📖 Glosario

| Término | Definición |
|---|---|
| **DIAN** | Dirección de Impuestos y Aduanas Nacionales de Colombia. Ente regulador de la facturación electrónica. |
| **CUFE** | Código Único de Factura Electrónica. Hash SHA-384 que garantiza la autenticidad de la factura. |
| **XML UBL** | Formato estructurado obligatorio para facturas electrónicas en Colombia (Universal Business Language). |
| **Evento DIAN** | Notificación oficial sobre el estado de una factura: acuse de recibo, aceptación expresa o rechazo. |
| **RUT** | Registro Único Tributario. Documento de identidad fiscal del emisor. |
| **Resolución de Facturación** | Autorización emitida por la DIAN al emisor para facturar electrónicamente con un rango de consecutivos. |
| **Verificación Gráfica** | Proceso que compara visualmente el PDF representación gráfica con los datos del XML para detectar inconsistencias. |

---

<p align="center">
  <sub>Desarrollado por el equipo Quipux · Colombia 🇨🇴</sub>
</p>
