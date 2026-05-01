"""Metadatos del servicio de logs de la aplicación.

Mensajes y constantes utilizados por el servicio de consulta de logs
para la página de logs del frontend.
"""


class MensajesLog:
    """Mensajes predefinidos para el servicio de logs."""

    completado = '{etapa} completado correctamente'
    """Mensaje cuando una etapa no tiene error. Acepta .format(etapa=...)."""

    error_prefijo = '{etapa} · {detalle}'
    """Formato para logs con error. Acepta .format(etapa=..., detalle=...)."""

    fuente_default = 'pipeline'
    """Fuente por defecto cuando el log no especifica una."""

    clave_fuente = 'fuente'
    """Clave del dict detalle_json para extraer la fuente del log."""

    clave_nivel = 'nivel'
    """Clave del dict detalle_json para extraer el nivel del log."""

    nivel_default = 'info'
    """Nivel por defecto cuando detalle_json no especifica uno."""

    nivel_error = 'error'
    """Identificador del nivel de error."""

    tipo_auto = 'auto'
    """Tipo de actividad para etapas completadas sin error."""
