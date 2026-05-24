# Análisis de Estado — Sistema de Facturación Electrónica QUIPUX

> **Fecha de análisis**: 9 de mayo de 2026  
> **Repositorios analizados**: `FacturacionElectronicaQx` (backend) · `quipuxaiprueba` (frontend)  
> **Fuentes de requisitos**: `requisitos_reto/`, `CONTEXT.md`, imágenes del reto

---

## 1. Lo que está listo ✅

### 1.1 Descarga Automática de Facturas (Req. 4.1)

| Funcionalidad | Estado | Archivos clave |
|---|---|---|
| Extracción automática desde correo Gmail | ✅ Implementado | `core/python/ingesta/email_listener.py` (44 KB) |
| Webhook de Gmail para disparo basado en eventos | ✅ Implementado | `routers/ingesta.py`, `scripts/gmail_trigger.js` |
| Clasificación por proveedor, fecha, tipo | ✅ Implementado | `utils/attachment_validator.py`, `utils/email_repository.py` |
| Almacenamiento S3 organizado por fecha | ✅ Implementado | `utils/s3_utils.py`, `metadata/path_s3.py` |
| Validación y extracción de ZIP (incl. anidados) | ✅ Implementado | `utils/attachment_validator.py` (profundidad max. 5 niveles) |
| Emparejamiento inteligente XML↔PDF | ✅ Implementado | `utils/attachment_validator.py` (por stem y por dígitos) |

### 1.2 Validación Automática Normativa DIAN (Req. 4.2)

Se implementaron **18 validadores individuales** en `core/python/validators/`:

| Validador | Archivo | Requisito DIAN cubierto |
|---|---|---|
| Denominación factura electrónica | `req_01_denominacion.py` | Tipo de documento electrónico |
| Datos del vendedor/emisor | `req_02_vendedor.py` | NIT, razón social, DV |
| Datos del adquiriente | `req_03_adquiriente.py` | NIT, razón social, DV |
| Numeración autorizada | `req_04_numeracion.py` | Rango DIAN, resolución, vigencia |
| Fecha de generación | `req_05_fecha_generacion.py` | Formato, no futura |
| Fecha de validación DIAN | `req_06_fecha_validacion.py` | Expedición DIAN |
| Validación DIAN del documento | `req_07_factura_validacion_dian.py` | Evento "Documento validado por la DIAN" |
| Ítems / líneas de factura | `req_08_items.py` | Descripción, cantidad, valor |
| Valor total | `req_09_valor.py` | Consistencia sumatoria |
| Forma de pago | `req_10_forma_pago.py` | Contado / crédito |
| Medio de pago | `req_11_medio_pago.py` | Catálogo DIAN completo |
| Calidad tributaria | `req_12_calidad_tributaria.py` | Gran contribuyente, autorretenedor, etc. |
| Impuestos | `req_13_impuestos.py` | IVA, INC, retenciones |
| Firma digital | `req_14_firma_digital.py` | Validación XML-DSig |
| CUFE | `req_15_cufe.py` | Extracción y validación |
| Código QR | `req_16_qr_code.py` | Extracción y consistencia |
| Anexo técnico UBL | `req_17_anexo_tecnico.py` | Cumplimiento estándar |
| Proveedor/software facturador | `req_18_proveedor_software.py` | Catálogo PT DIAN |
| Verificación gráfica PDF vs XML | `validacion_grafica.py` | Cascada heurística + IA |

**Flujo de procesamiento completo**: `core/python/facturas/invoice_processor.py` (40 KB) orquesta todas las validaciones, con:
- Pipeline secuencial de validaciones
- Registro de cada paso en `PROCESO_INGESTA` + `LOG_PROCESO`
- Persistencia de la factura en `FACTURA` con todas las entidades relacionadas
- Política de reintentos con máximo configurable

**Correo de rechazo al proveedor (Req. 4.2 — "Si NO cumple")**:

| Funcionalidad | Estado | Archivos clave |
|---|---|---|
| Handler de rechazos con registro en BD | ✅ Implementado | `core/python/rechazos/rechazo_handler.py` |
| Envío SMTP con política de reintentos (exponential backoff) | ✅ Implementado | `core/python/rechazos/email_sender.py` |
| Plantilla de correo de rechazo | ✅ Implementado | `input/email/plantilla_rechazo.txt` |
| Registro en tabla DEVOLUCION con estado (PENDIENTE/ENVIADO/FALLIDO) | ✅ Implementado | Tabla `FACTURACION.DEVOLUCION` |
| Integración en pipeline de ingesta | ✅ Implementado | `email_listener.py` — invocado en 4 escenarios: sin adjuntos (L719), rechazado por filtro (L732), fallo de descarga (L765), sin pares procesables (L821) |

### 1.3 Alertas de Incumplimientos (Req. 4.3)

| Funcionalidad | Estado | Archivos clave |
|---|---|---|
| Sistema de alertas con 4 niveles de prioridad | ✅ Implementado | `utils/alerts.py`, `utils/alertas_repository.py` |
| Alerta por ZIP sin XML/PDF | ✅ Implementado | `AlertManager.adjunto_incompleto()` |
| Alerta por malware detectado | ✅ Implementado | `AlertManager.malware_detectado()` |
| Alerta por vencimiento próximo | ✅ Implementado | `AlertManager.vencimiento_proximo()` |
| Alerta por factura rechazada | ✅ Implementado | `AlertManager.factura_rechazada()` |
| Alerta por bot inactivo | ✅ Implementado | `AlertManager.bot_inactivo()` |
| Alerta por conexión fallida | ✅ Implementado | `AlertManager.error_conexion()` |
| Alerta por max reintentos | ✅ Implementado | `AlertManager.max_reintentos_excedido()` |
| Envío de correo para alertas CRITICAS | ✅ Implementado | `utils/email_sender.py` (SMTP Gmail) |
| Persistencia de alertas en BD | ✅ Implementado | Tabla `FACTURACION.ALERTA` con FK a correo/adjunto/factura |

### 1.4 Seguridad y Acceso (Lineamiento 5.1)

| Requisito | Estado | Detalle |
|---|---|---|
| Autenticación OAuth2 | ✅ Implementado | `core/python/auth/security.py`, `routers/auth.py` (JWT Bearer) |
| Protección de archivos (malware) | ✅ Implementado | `utils/malware_scanner.py` + ClamAV daemon en Docker |
| Validación de identidad (magic numbers) | ✅ Implementado | `utils/security_utils.py` con `python-magic` |
| Extensiones prohibidas | ✅ Implementado | `.exe, .bat, .sh, .js, .vbs, .msi, .scr, .pif` |

### 1.5 Gestión de Datos y Cumplimiento (Lineamiento 5.2)

| Requisito | Estado | Detalle |
|---|---|---|
| Integridad XML vs Firma Digital | ✅ Implementado | `req_14_firma_digital.py` valida XML-DSig |
| Trazabilidad (Log detallado) | ✅ Implementado | `PROCESO_INGESTA` + `LOG_PROCESO` en BD, logging Python |
| Idempotencia | ✅ Implementado | SHA256 en adjuntos, CUFE UNIQUE, `ON CONFLICT DO NOTHING` |

### 1.6 Performance y Escalabilidad (Lineamiento 5.3)

| Requisito | Estado | Detalle |
|---|---|---|
| Arquitectura basada en eventos | ✅ Implementado | Webhook Gmail → BackgroundTasks |
| Base de datos indexada | ✅ Implementado | 12+ índices en el schema SQL |
| Pool de conexiones async | ✅ Implementado | `core/python/db/` con psycopg async pool |

### 1.7 Confiabilidad (Lineamiento 5.4)

| Requisito | Estado | Detalle |
|---|---|---|
| Idempotencia | ✅ Implementado | `ON CONFLICT DO NOTHING` en correos, adjuntos, facturas |
| Alertas de sistema | ✅ Implementado | `AlertManager` con persistencia BD + email |
| Tabla de devoluciones | ✅ Implementado | `FACTURACION.DEVOLUCION` con estado de notificación |

### 1.8 Atributos de Valor (Lineamiento 5.5)

| Requisito | Estado | Detalle |
|---|---|---|
| Mantenibilidad (reglas separadas) | ✅ Implementado | Cada validación DIAN es un módulo independiente en `validators/` |
| Configuración externalizada | ✅ Implementado | `config/settings.yaml`, `config/tool_definitions.yml`, YAML de queries |
| Catálogos DIAN como datos | ✅ Implementado | 12 tablas `TIPO_*` pre-pobladas en el SQL |

### 1.9 Infraestructura (Lineamiento 6)

| Componente | Estado | Detalle |
|---|---|---|
| Amazon S3 | ✅ Implementado | `utils/s3_utils.py`, credenciales en YAML |
| IA Generativa (justificada) | ✅ Implementado | Chatbot Innti (LLM + function calling), verificación gráfica con IA |
| Docker Compose completo | ✅ Implementado | BD, ClamAV, API, Frontend, Caddy/nginx-proxy |

### 1.10 Base de Datos

Schema completo en `modelo_facturacion.sql` (821 líneas, 46 KB):
- **12 tablas de catálogo** (`TIPO_*`) pre-pobladas con datos DIAN oficiales
- **90+ proveedores tecnológicos** del catálogo DIAN
- **Tabla USUARIO** con auth bcrypt
- **Flujo completo**: CORREO_ENTRANTE → ADJUNTOS_CORREO → EVENTO_INGESTA → PROCESO_INGESTA → FACTURA
- **Entidades normalizadas**: TERCERO, AUTORIZACION_NUMERACION, DETALLE_FACTURA, IMPUESTO_FACTURA, PAGO_FACTURA, etc.

### 1.11 Frontend (quipuxaiprueba)

| Componente | Estado | Detalle |
|---|---|---|
| Stack tecnológico | ✅ | React + Vite + TanStack Router + TypeScript + shadcn/ui |
| Página de Login | ✅ | `src/routes/login.tsx` + `src/components/auth/LoginForm.tsx` |
| Dashboard principal | ✅ | KPIs, pipeline visual, gráficos (barras, pie, tendencia, heatmap) |
| Panel de alertas | ✅ | `AlertsPanel.tsx` con prioridades |
| Panel de actividad | ✅ | `ActivityPanel.tsx` con eventos/min |
| Tabla de facturas | ✅ | `InvoicesTable.tsx` dentro del dashboard |
| Página de facturas con filtros | ✅ | `src/routes/facturas.tsx` con estadísticas |
| Página de logs | ✅ | `src/routes/logs.tsx` con niveles |
| Chatbot Innti | ✅ | `ChatPanel.tsx` integrado con `/api/chat` |
| Autenticación JWT | ✅ | `use-auth.tsx` con contexto React |
| Hooks de datos | ✅ | `use-dashboard.ts`, `use-facturas.ts`, `use-logs.ts`, etc. |
| Skeletons de carga | ✅ | `CardLoader.tsx` con estados de loading |
| Despliegue Docker | ✅ | `Dockerfile` + nginx.conf |

### 1.12 API REST

| Endpoint | Método | Funcionalidad |
|---|---|---|
| `/api/dashboard` | GET | Dashboard completo (KPIs, pipeline, gráficos) |
| `/api/facturas` | GET | Listado paginado con filtros y estadísticas |
| `/api/proveedores` | GET | Proveedores con métricas |
| `/api/validaciones` | GET | Reglas de validación con conteos |
| `/api/rechazos` | GET | Rechazos con causas frecuentes |
| `/api/logs` | GET | Logs del sistema con niveles |
| `/api/chat` | POST | Chatbot Innti (LLM + function calling) |
| `/api/auth/token` | POST | Login OAuth2 (JWT) |
| `/api/auth/me` | GET | Usuario autenticado |
| `/webhook/gmail` | POST | Ingesta desde Gmail |

---

## 2. Lo que falta ⚠️

### P0 — Bloqueante

*No se identificaron bloqueantes P0.* El sistema tiene los componentes esenciales para funcionar end-to-end.

---

### P1 — Crítico

| # | Descripción | Repo | Justificación |
|---|---|---|---|
| **P1-1** | **Revisión automática de eventos DIAN (Req. 4.4)** — No hay un módulo que monitoree el correo de notificaciones de la DIAN para actualizar automáticamente el estado de las facturas (`recibida → aceptada → rechazada → en disputa`). La tabla `EVENTO_DIAN_FACTURA` existe en la BD y los eventos se extraen del XML durante la ingesta (req_07), pero **no hay un listener separado** que monitoree el correo de eventos DIAN en tiempo real. | Backend | Requisito funcional principal del reto (§4.4). Sin esto, la transición de estados depende exclusivamente del XML recibido, no del monitoreo continuo del buzón DIAN. |
| **P1-2** | **Cifrado de datos en reposo (AES-256)** — No se implementó cifrado a nivel de aplicación ni se configuró cifrado de volumen/S3. Los archivos se almacenan en S3 sin configuración explícita de server-side encryption. | Backend | Lineamiento obligatorio §5.1. |
| **P1-3** | **Cifrado en tránsito (TLS 1.2+)** — La API corre en HTTP plano (uvicorn sin TLS). El `Caddyfile` existe pero la configuración de TLS automático no está validada; el frontend usa nginx sin configuración HTTPS visible. | Ambos | Lineamiento obligatorio §5.1. Para producción es necesario HTTPS. |

---

### P2 — Importante

| # | Descripción | Repo | Justificación |
|---|---|---|---|
| **P2-1** | **Exportación/descarga de datos como Excel de control (Req. 4.2 / 4.5)** — El dashboard del frontend muestra datos en tiempo real con filtros por fecha, cubriendo las necesidades del "reporte inteligente" (§4.5). Sin embargo, **no se implementó la funcionalidad de descarga/exportación a Excel**. El §4.2 menciona "actualizar Excel de control" como artefacto de salida. Se necesita: (a) endpoint backend `GET /api/facturas/export` que genere el Excel, y (b) botón de descarga en el frontend (el icono `Download` ya está importado en `facturas.tsx` pero no tiene funcionalidad). | Ambos | El Excel de control es un artefacto de salida explícito del reto (§4.2). El frontend ya tiene los datos y la UI, solo falta la descarga. |
| **P2-2** | **Procesamiento asíncrono con colas de trabajo** — El sistema usa `BackgroundTasks` de FastAPI (un thread pool básico). El archivo `core/python/ingesta/queue_publisher.py` (4 KB) existe pero **no se evidencia un worker/consumer con cola real** (ej. Celery, RabbitMQ, Redis Queue). Para múltiples facturas en paralelo esto puede ser un cuello de botella. | Backend | Lineamiento §5.3: "Uso de colas de trabajo para procesar múltiples facturas en paralelo". |
| **P2-3** | **Política de reintentos para servicios DIAN** — Existe lógica de reintentos a nivel de `EVENTO_INGESTA.INTENTOS`, pero **no hay una política formal de retry con backoff** para cuando los servicios DIAN estén caídos. | Backend | Lineamiento §5.4: "Política automática si servicios DIAN están caídos". |
| **P2-4** | **Cumplimiento Habeas Data (Ley 1581)** — No se identificó un módulo de consentimiento, anonimización o gestión de datos personales de proveedores. Los datos de terceros se almacenan sin política de retención ni mecanismo de eliminación. | Backend | Lineamiento §5.2: privacidad. |
| **P2-5** | **Protección de endpoints con JWT** — Solo `/api/auth/me` usa `get_current_active_user`. Los demás endpoints (`/api/dashboard`, `/api/facturas`, `/api/chat`, etc.) **son públicos**. No hay middleware de autenticación global. | Backend | §5.1 Seguridad: toda la API debería estar protegida. |
| **P2-6** | **Página de proveedores en frontend** — El hook `use-proveedores.ts` y endpoint `/api/proveedores` existen, pero **no hay ruta/página** en el frontend (`src/routes/`) para proveedores. | Frontend | El dashboard muestra gráfico de barras, pero no hay vista detallada. |
| **P2-7** | **Página de validaciones en frontend** — El hook `use-validaciones.ts` y endpoint `/api/validaciones` existen, pero **no hay ruta/página** dedicada. | Frontend | Mejoraría la observabilidad del sistema. |
| **P2-8** | **Página de rechazos en frontend** — Similar: hook y endpoint listos, sin ruta en el frontend. | Frontend | Requerimiento de base de devoluciones (§4.2). |

---

### P3 — Deseable

| # | Descripción | Repo | Justificación |
|---|---|---|---|
| **P3-1** | **Tests de validadores DIAN** — Solo existen tests de la ingesta de email (`tests/test_email_parser.py`, `test_with_zip.py`, etc.). No hay tests para los 18 validadores del `core/python/validators/`. | Backend | Cobertura de pruebas; asegurar correctitud de reglas DIAN. |
| **P3-2** | **RUT vigente** — El req. 4.2 menciona validar "RUT vigente". No se identificó un validador que consulte la vigencia del RUT del emisor (la tabla `TERCERO` almacena el NIT pero no su estado DIAN). | Backend | Validación secundaria; requeriría integración con servicios DIAN. |
| **P3-3** | **Resolución de facturación vigente (consulta a DIAN)** — `req_04_numeracion.py` valida la información del XML, pero **no consulta activamente** si la resolución sigue vigente en la DIAN. | Backend | Validación complementaria para mayor rigurosidad. |
| **P3-4** | **Panel de control en tiempo real (WebSocket)** — El dashboard hace polling cada 30s (`refetchInterval: 30_000`). No hay WebSocket ni SSE para actualizaciones push en tiempo real. | Ambos | Lineamiento §5.5: "Panel de control en tiempo real". Polling funciona, WebSocket mejoraría UX. |
| **P3-5** | **Documentación de API (OpenAPI)** — FastAPI genera Swagger automáticamente, pero no se ha personalizado la documentación con ejemplos o modelos Pydantic para todos los endpoints. | Backend | Buenas prácticas de API pública. |
| **P3-6** | **Manejo de creación de carpeta del día** — §4.2 menciona "crear carpeta del día" para facturas válidas. La organización en S3 ya es por fecha, pero no hay lógica de carpetas locales. | Backend | Menor prioridad; S3 ya cumple la función. |

---

## 3. Plan de Acción

### Fase 1 — Seguridad y protección (2-3 días)

| Paso | Tarea | Prioridad | Dependencia |
|---|---|---|---|
| 1.1 | **Proteger todos los endpoints con JWT** — Crear middleware/dependencia global de autenticación y aplicarla a todos los routers excepto `/api/auth/token` y `/`. | P2-5 | — |
| 1.2 | **Configurar TLS** — Ajustar Caddyfile para HTTPS automático en producción y documentar la configuración. | P1-3 | — |
| 1.3 | **Configurar cifrado S3** — Habilitar `ServerSideEncryption=AES256` en todas las llamadas a `s3_client.upload_file()`. | P1-2 | — |

### Fase 2 — Funcionalidades core faltantes (3-5 días)

| Paso | Tarea | Prioridad | Dependencia |
|---|---|---|---|
| 2.1 | **Implementar listener de eventos DIAN** — Crear un nuevo listener (o extender `EmailListener`) que monitoree el correo de notificaciones DIAN, parsee los `ApplicationResponse` y actualice `EVENTO_DIAN_FACTURA` + el estado de la factura en la tabla `FACTURA`. | P1-1 | — |
| 2.2 | **Exportación/descarga Excel de control** — Crear endpoint backend `GET /api/facturas/export` que genere un Excel (openpyxl) con los datos de facturas filtrados. Conectar el botón `Download` que ya existe en `facturas.tsx` para descargar el archivo. Incluir: facturas pendientes, rechazadas, sin evento DIAN, antigüedad de cartera. | P2-1 | — |
| 2.3 | **Implementar cola de trabajo** — Reemplazar `BackgroundTasks` por un sistema de colas (ej. Redis Queue + worker) para procesamiento paralelo de facturas. | P2-2 | — |

### Fase 3 — Frontend y UX (3-4 días)

| Paso | Tarea | Prioridad | Dependencia |
|---|---|---|---|
| 3.1 | **Crear página de proveedores** — Nueva ruta `src/routes/proveedores.tsx` consumiendo `use-proveedores.ts`. | P2-6 | — |
| 3.2 | **Crear página de validaciones** — Nueva ruta `src/routes/validaciones.tsx`. | P2-7 | — |
| 3.3 | **Crear página de rechazos** — Nueva ruta `src/routes/rechazos.tsx` con detalle de devoluciones. | P2-8 | — |

### Fase 4 — Calidad y cumplimiento (2-3 días)

| Paso | Tarea | Prioridad | Dependencia |
|---|---|---|---|
| 4.1 | **Tests de validadores DIAN** — Escribir tests unitarios para cada `req_*.py` con XMLs de prueba (válidos e inválidos). | P3-1 | — |
| 4.2 | **Política de reintentos con backoff** — Implementar exponential backoff en `invoice_processor.py` para servicios DIAN. | P2-2 | — |
| 4.3 | **Documentar política Habeas Data** — Crear documento de política y, como mínimo, implementar endpoint de eliminación de datos de terceros. | P2-3 | — |

---

## Resumen ejecutivo

| Categoría | Completado | Pendiente |
|---|---|---|
| Funcionalidades core (§4.1-4.5) | 4 de 5 (descarga, validación, alertas, correo rechazo + dashboard tiempo real como reporte) | 1 (Listener eventos DIAN) + descarga Excel |
| Lineamientos técnicos (§5.1-5.5) | 8 de 12 | 4 (Cifrado, colas, Habeas Data, auth global) |
| Backend — Módulos | 18 validadores + ingesta + alertas + rechazos + chat + auth | Eventos DIAN, export Excel |
| Frontend — Páginas | 4 (Dashboard, Facturas, Logs, Login) | 3 (Proveedores, Validaciones, Rechazos) |
| Tests | Ingesta (4 archivos) | Validadores DIAN (0 tests) |
| Infraestructura | Docker completo (DB, ClamAV, API, Frontend) | TLS, cifrado S3 |

> **Estado general**: El sistema tiene una base muy sólida con un pipeline de ingesta funcional, 18 validaciones DIAN, sistema de alertas completo, correo de rechazo automático al proveedor funcionando, chatbot con IA y un frontend moderno con dashboard en tiempo real. El único P1 restante es el listener de eventos DIAN. Los demás pendientes son P2/P3 y son alcanzables en ~1 semana.
