"""Metadatos compartidos del sistema.

Textos por defecto y constantes genéricas reutilizadas en múltiples módulos.
"""


class DefaultTextos:
    """Textos por defecto para campos vacíos o ausentes."""

    sin_nombre = 'Sin nombre'
    """Placeholder cuando el nombre comercial de un tercero es NULL. Usado en servicios y chat tools."""

    sin_contacto = 'Sin contacto'
    """Placeholder cuando no hay correo ni teléfono de contacto. Usado en chat/tools.py (listar_proveedores)."""

    no_aplica = 'N/A'
    """Texto genérico para campos que no aplican o no tienen valor. Usado en chat/tools.py y servicios."""

    sin_fecha = 'Sin fecha'
    """Placeholder cuando una fecha de factura es NULL. Usado en chat/tools.py (buscar_facturas)."""

    sin_monto = '$0'
    """Placeholder cuando el valor total de una factura es NULL o cero. Usado en chat/tools.py."""

    sin_monto_detalle = 'Sin monto'
    """Placeholder cuando el monto de una factura es NULL en vista de detalle. Usado en chat/tools.py (detalle_factura)."""

    factura_electronica = 'Factura electrónica'
    """Tipo de documento por defecto para mostrar en la UI. Usado en facturas_service.py y dashboard_service.py."""

    error_no_especificado = 'Error no especificado'
    """Texto cuando la descripción del error de rechazo es NULL. Usado en rechazos_service.py."""

    error_generico_regla = 'ERR-GEN'
    """Código de regla genérico cuando el código de respuesta es NULL. Usado en rechazos_service.py."""

    estado_ok = 'OK'
    """Etiqueta de estado exitoso en logs. Usado en chat/tools.py (ver_logs_recientes)."""

    estado_error = 'ERROR'
    """Etiqueta de estado de error en logs. Usado en chat/tools.py (ver_logs_recientes)."""

    formato_fecha_hora = '%d/%m/%Y %H:%M'
    """Formato estándar de fecha y hora para presentación al usuario. Usado en chat/tools.py."""

    formato_fecha = '%d/%m/%Y'
    """Formato estándar de solo fecha para presentación al usuario. Usado en chat/tools.py."""

    formato_fecha_corto = '%d/%m %H:%M'
    """Formato corto de fecha con hora para tablas y listas. Usado en servicios del frontend."""

    formato_hora = '%H:%M:%S'
    """Formato de solo hora. Usado en logs_service.py para timestamps."""
