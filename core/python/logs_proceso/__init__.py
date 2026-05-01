"""Paquete de registro de procesos de ingesta.

Re-exporta la función principal para facilitar imports:
    from core.python.logs_proceso import registrar_proceso_ingesta
"""

from core.python.logs_proceso.insertar_log_proceso import registrar_proceso_ingesta

__all__ = [
    'registrar_proceso_ingesta',
]
