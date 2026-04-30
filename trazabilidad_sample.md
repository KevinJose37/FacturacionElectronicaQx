# Ejemplo de Uso del Sistema de Trazabilidad

Este documento muestra cómo utilizar el sistema de logs de trazabilidad implementado en el proyecto para registrar cada etapa del proceso de facturación electrónica.

## 1. Importaciones Necesarias

Para registrar logs, debes importar la función core y las clases de metadatos correspondientes:

```python
import json
from core.trazabilidad_core import registrar_log_etapa
from metadata.log_metadata import (
    EtapasProceso, 
    EstadosProceso, 
    MensajesError, 
    EstructurasDetalle
)
```

## 2. Escenario: Recepción Exitosa

Cuando se detecta un correo y se procesa correctamente la primera etapa:

```python
# Datos dinámicos del proceso
id_proceso_actual = 50
uid_correo = "789"
host_servidor = "imap.empresa.com"

# 1. Preparar el detalle JSON usando la estructura de metadatos
detalle_json_str = EstructurasDetalle.recepcion_email.format(
    uid=uid_correo,
    host=host_servidor
)

# 2. Registrar el log
registrar_log_etapa(
    id_proceso=id_proceso_actual,
    codigo_etapa=EtapasProceso.recepcion_email,
    codigo_estado=EstadosProceso.recibido,
    detalle_json=json.loads(detalle_json_str)
)
```

## 3. Escenario: Error en el Proceso

Si ocurre un fallo técnico (por ejemplo, no se encuentra el archivo ZIP):

```python
registrar_log_etapa(
    id_proceso=id_proceso_actual,
    codigo_etapa=EtapasProceso.verificacion_adjuntos,
    codigo_estado=EstadosProceso.error,
    detalle_error=MensajesError.error_sin_zip
)
```

## 4. Funcionamiento Interno

Al llamar a `registrar_log_etapa`:
1.  **Resolución de IDs**: El sistema consulta la base de datos (vía `config/queries_trazabilidad.yml`) para traducir el código de estado (ej: `'RECIBIDO'`) al ID numérico real.
2.  **Auto-secuencia**: Calcula el siguiente `NUMERO_SECUENCIA` disponible para ese `ID_PROCESO`.
3.  **Persistencia**: Inserta el registro en la tabla `FACTURACION.LOG_PROCESO` con la fecha actual automática.

---
*Este sistema garantiza que la trazabilidad sea consistente, fácil de auditar y resistente a cambios en los IDs de la base de datos.*
