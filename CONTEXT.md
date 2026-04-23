# CONTEXT.md — Sistema Inteligente de Facturación Electrónica
 
> Documento de contexto para agentes. Contiene toda la información necesaria para entender el proyecto, sus requisitos, lineamientos técnicos y restricciones.
 
---
 
## 1. Identidad del Agente Experto
 
- **Rol base**: Arquitecto de software senior.
- **Lenguaje principal**: Python.
- **Dominio especializado**: Facturación electrónica en Colombia (normativa DIAN).
---
 
## 2. Problema
 
El área de facturación de una empresa colombiana enfrenta un **cuello de botella** en la revisión de facturas electrónicas de proveedores. Los síntomas son:
 
- Alto consumo de tiempo humano en tareas repetitivas de revisión.
- Alta propensión a errores manuales durante la validación.
- Riesgo tributario por incumplimiento normativo DIAN.
- Reprocesos administrativos por rechazos y devoluciones.
---
 
## 3. Objetivo
 
Diseñar la **arquitectura de un sistema inteligente** que automatice el ciclo completo de:
 
1. Recepción de facturas electrónicas.
2. Validación normativa.
3. Control y seguimiento del estado de cada factura.
**Restricción temporal**: 1 mes y medio (≈ 6 semanas) de desarrollo.
 
---
 
## 4. Funcionalidades Requeridas
 
### 4.1 Descarga Automática de Facturas
- Extracción automática desde el **correo de facturación** (bandeja de entrada).
- Clasificación por: proveedor, fecha y tipo de documento.
### 4.2 Validación Automática Normativa DIAN
- Validar: **CUFE**, XML bien formado, resolución de facturación vigente, RUT vigente, eventos DIAN.
- **Si cumple**:
  - Crear carpeta del día.
  - Guardar archivos: ZIP, XML, PDF.
  - Actualizar Excel de control.
- **Si NO cumple**:
  - Generar listado de inconsistencias.
  - Enviar correo de rechazo al proveedor.
  - Registrar en base de devoluciones.
### 4.3 Alertas de Incumplimientos
- Notificación si no llegan: ZIP, XML o eventos DIAN esperados.
- Alerta si se acerca la **fecha de vencimiento** sin aceptación registrada.
### 4.4 Revisión Automática de Eventos DIAN
- Monitoreo del **correo de notificaciones DIAN**.
- Actualización automática del estado de cada factura:
  - `recibida` → `aceptada` → `rechazada` → `en disputa`
### 4.5 Reporte Inteligente Semanal
- Facturas pendientes por vencer.
- Facturas rechazadas.
- Facturas sin evento DIAN registrado.
- Antigüedad de cartera por proveedor.
---
 
## 5. Lineamientos Técnicos Obligatorios
 
### 5.1 Seguridad y Acceso
| Aspecto | Requisito |
|---|---|
| Autenticación | OAuth2 |
| Cifrado en reposo | AES-256 |
| Cifrado en tránsito | TLS 1.2+ |
| Protección de archivos | Validación de identidad de archivos para prevenir malware disfrazado de XML/PDF |
 
### 5.2 Gestión de Datos y Cumplimiento Legal
| Aspecto | Requisito |
|---|---|
| Integridad | Validación estricta del XML vs. Firma Digital (el documento no debe haber sido alterado) |
| Trazabilidad | Log detallado de cada etapa del proceso (para auditorías tributarias) |
| Privacidad | Cumplimiento de **Habeas Data (Ley 1581 de Colombia)** en datos de proveedores |
 
### 5.3 Performance y Escalabilidad
| Aspecto | Requisito |
|---|---|
| Procesamiento | Asíncrono mediante **colas de trabajo** (múltiples facturas en paralelo) |
| Arquitectura | **Basada en eventos** (se activa al llegar el correo) |
| Base de datos | Indexada antes de exportar a Excel para reportes rápidos |
 
### 5.4 Confiabilidad (Resiliencia)
| Aspecto | Requisito |
|---|---|
| Reintentos | Política automática si servicios DIAN están caídos |
| Idempotencia | Una factura NO puede procesarse ni registrarse dos veces |
| Alertas de sistema | Notificación inmediata si el bot de extracción falla |
 
### 5.5 Atributos de Valor
| Aspecto | Requisito |
|---|---|
| Mantenibilidad | Separar las reglas de negocio DIAN del código base (configuración externa) |
| Observabilidad | Panel de control en tiempo real del estado de las facturas |
 
---
 
## 6. Infraestructura Disponible
 
- **Almacenamiento en la nube**: Amazon S3 (bucket disponible para uso).
- **IA generativa**: Permitida únicamente en casos donde **agregue valor real y demostrable**.
---
 
## 7. Salidas Esperadas del Sistema
 
El sistema debe producir como artefactos de diseño:
 
1. **Planteamiento de la arquitectura** del sistema inteligente de facturación (cumpliendo todos los requisitos y lineamientos).
2. **Propuesta tecnológica** con sustento técnico para cada componente.
3. **Flujo de trabajo de desarrollo** con división de roles para el equipo disponible.
---
 
## 8. Equipo de Desarrollo Disponible
 
| Rol | Cantidad |
|---|---|
| Desarrolladores | 3 |
| Analista de datos | 1 |
 
**Tiempo total de proyecto**: ~6 semanas (1 mes y medio).
 
---
 
## 9. Entidades y Conceptos Clave del Dominio
 
| Término | Definición |
|---|---|
| **DIAN** | Dirección de Impuestos y Aduanas Nacionales de Colombia. Ente regulador de la facturación electrónica. |
| **CUFE** | Código Único de Factura Electrónica. Identificador único que garantiza autenticidad de la factura. |
| **XML** | Formato estructurado obligatorio para facturas electrónicas en Colombia. |
| **RUT** | Registro Único Tributario. Documento de identidad fiscal del proveedor. |
| **Evento DIAN** | Notificación oficial de la DIAN sobre el estado de una factura (acuse de recibo, aceptación, rechazo). |
| **ZIP** | Paquete comprimido que contiene XML + PDF de la factura electrónica. |
| **Habeas Data** | Ley 1581 de 2012. Norma colombiana de protección de datos personales. |
| **Resolución de facturación** | Autorización emitida por la DIAN al emisor para facturar electrónicamente. |
 
---
 
## 10. Restricciones y Consideraciones Críticas
 
- El sistema **no debe procesar una misma factura dos veces** (idempotencia obligatoria).
- Los servicios DIAN tienen **disponibilidad variable**; el sistema debe manejar indisponibilidades sin perder datos.
- Los archivos recibidos por correo pueden ser **maliciosos**; toda entrada debe ser validada y sanitizada.
- El Excel de control es un **artefacto de salida**, no la fuente de verdad; la base de datos indexada es el sistema de registro.
- El uso de agentes de IA debe **justificarse técnicamente** en cada caso de uso propuesto.
---
 
*Generado automáticamente para ser consumido por agentes de arquitectura, desarrollo y análisis dentro del proyecto.*