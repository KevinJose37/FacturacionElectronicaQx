"""Metadatos del chatbot Innti.

Mensajes predefinidos para respuestas vacías o de error en las tools del LLM,
system prompt, errores HTTP y plantillas de contexto.
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
    """Respuesta cuando detalle_factura no encuentra la factura. Acepta .format(identificador=...)."""

    falta_identificador = 'Debes especificar un número de factura o CUFE para buscar.'
    """Respuesta cuando detalle_factura se invoca sin parámetros."""

    tool_desconocida = 'Tool desconocida: {name}'
    """Respuesta cuando execute_tool recibe un nombre de tool que no existe. Acepta .format(name=...)."""

    error_ejecucion = 'Error al ejecutar la consulta: {error}'
    """Respuesta cuando una tool lanza excepción. Acepta .format(error=...)."""


class ErroresChat:
    """Mensajes de error HTTP del endpoint del chatbot."""

    no_configurado = 'Chatbot no configurado. Faltan LLM_BASE_URL y/o LLM_API_KEY en .env'
    """Error 503 cuando las credenciales del LLM no están en variables de entorno."""

    error_ia = 'Error del servicio de IA (status {status})'
    """Error 502 cuando el LLM responde con error. Acepta .format(status=...)."""

    timeout_ia = 'El servicio de IA tardó demasiado en responder. Intenta de nuevo.'
    """Error 504 cuando la llamada al LLM excede el timeout."""

    conexion_ia = 'No se pudo conectar con el servicio de IA.'
    """Error 502 cuando no se puede conectar al endpoint del LLM."""

    respuesta_inesperada = 'Respuesta inesperada del servicio de IA.'
    """Error 502 cuando la estructura de respuesta del LLM no es la esperada."""

    fallback_sin_respuesta = (
        'Lo siento, actualmente no puedo procesar esta solicitud específica o realizar esta acción. '
        'Si es una funcionalidad avanzada que no está contemplada en el menú actual, es muy probable que '
        'la estemos integrando en futuras versiones de Innti Assistant. Por favor, intenta reformular tu consulta '
        'o solicita información sobre facturas, proveedores, rechazos o logs del sistema.'
    )
    """Respuesta por defecto cuando se agotan las iteraciones de tool calling."""


class MensajesLogChat:
    """Mensajes de log del chatbot."""

    contexto_error = 'Error obteniendo contexto para chat: %s'
    """Warning cuando falla la obtención de contexto del sistema."""

    contexto_fallback = '\n[No se pudieron obtener datos del sistema en este momento.]\n'
    """Texto de fallback inyectado en el prompt cuando falla el contexto."""

    llm_api_error = 'LLM API error: status=%d body=%s'
    """Error de API del LLM con código y cuerpo truncado."""

    tools_solicitadas = 'LLM solicitó %d tool(s) en iteración %d'
    """Info cuando el LLM solicita ejecutar tools."""

    tool_ejecutando = 'Ejecutando tool: %s(%s)'
    """Info al ejecutar una tool específica."""

    llm_timeout = 'LLM API timeout after %ds'
    """Error cuando la llamada al LLM excede el timeout."""

    llm_conexion_error = 'LLM API connection error: %s'
    """Error de conexión al LLM."""

    llm_formato_error = 'LLM API unexpected response format: %s'
    """Error cuando el formato de respuesta del LLM es inesperado."""


class SystemPrompt:
    """System prompt base del chatbot Innti."""

    base = (
        'Eres **Innti**, el asistente inteligente de **QUIPUX Director Apolo**, '
        'un sistema de facturación electrónica colombiana.\n\n'
        'Tu rol:\n'
        '- Ayudar al usuario a entender el estado del sistema de facturación.\n'
        '- Responder preguntas sobre facturas, proveedores, validaciones, rechazos y logs.\n'
        '- Ser conciso, profesional y amigable. Responde siempre en español.\n'
        '- Usa datos reales del sistema que se te proporcionan abajo.\n'
        '- Si no tienes datos suficientes para una pregunta específica, indícalo claramente.\n'
        '- No inventes datos. Si el dato no está en el contexto proporcionado, '
        'di que no lo tienes disponible.\n'
        '- Puedes formatear tus respuestas con markdown básico (negritas, listas, etc).\n\n'
        'Contexto del sistema:\n'
        '- El sistema procesa facturas electrónicas colombianas (FE, NC, ND, DS).\n'
        '- Las facturas pasan por un pipeline: Recepción → Verificación → Escaneo '
        '→ Parsing XML → Validación DIAN → Persistencia.\n'
        '- Los estados posibles son: pendiente, validada, rechazada, error.\n'
        '- Los rechazos pueden ser por CUFE inválido, NIT no registrado, XML mal formado, etc.\n'
    )
    """Prompt base que se concatena con el contexto del sistema."""
