"""Metadatos del módulo de registro de procesos de ingesta.

Mensajes de log y error para la inserción en PROCESO_INGESTA.
"""


class MensajesLogProceso:
    """Mensajes de log para el registro de procesos de ingesta."""

    registro_exitoso = 'Proceso de ingesta registrado (ID=%s): %s'
    """Info al insertar exitosamente un registro. Usado en insertar_log_proceso.py."""

    error_registro = 'Error al registrar proceso de ingesta: %s'
    """Error al fallar la inserción en PROCESO_INGESTA. Usado en insertar_log_proceso.py."""
