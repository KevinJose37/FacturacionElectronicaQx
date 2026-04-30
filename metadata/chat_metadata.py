"""Metadatos del chatbot Innti.

Mensajes predefinidos para respuestas vacías o de error en las tools del LLM.
"""


class MensajesRespuesta:
    """Mensajes predefinidos para respuestas vacías en chat tools."""

    sin_facturas = 'No se encontraron facturas con los filtros especificados.'
    """Respuesta cuando buscar_facturas no retorna resultados. Usado en chat/tools.py."""

    sin_proveedores = 'No se encontraron proveedores.'
    """Respuesta cuando listar_proveedores no retorna resultados. Usado en chat/tools.py."""

    sin_rechazos = 'No se encontraron rechazos con los filtros especificados.'
    """Respuesta cuando buscar_rechazos no retorna resultados. Usado en chat/tools.py."""

    sin_logs = 'No se encontraron logs recientes.'
    """Respuesta cuando ver_logs_recientes no retorna resultados. Usado en chat/tools.py."""

    sin_factura_detalle = 'No se encontró factura con número "{identificador}".'
    """Respuesta cuando detalle_factura no encuentra la factura. Acepta .format(identificador=...). Usado en chat/tools.py."""

    falta_identificador = 'Debes especificar un número de factura o CUFE para buscar.'
    """Respuesta cuando detalle_factura se invoca sin parámetros. Usado en chat/tools.py."""

    tool_desconocida = 'Tool desconocida: {name}'
    """Respuesta cuando execute_tool recibe un nombre de tool que no existe. Acepta .format(name=...). Usado en chat/tools.py."""

    error_ejecucion = 'Error al ejecutar la consulta: {error}'
    """Respuesta cuando una tool lanza excepción. Acepta .format(error=...). Usado en chat/tools.py."""
