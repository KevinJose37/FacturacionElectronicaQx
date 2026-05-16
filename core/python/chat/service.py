"""Servicio del chatbot Innti — lógica de negocio del LLM.

Encapsula la construcción de contexto, comunicación con el LLM
y el ciclo de function calling. El router solo delega aquí.
"""

import asyncio
import json
import logging

import httpx

from config import get_config, load_yaml_config
from core.python.chat import tools as chat_tools
from core.python.db import cached
from core.python.services import dashboard_service, facturas_service, rechazos_service
from metadata.chat_metadata import ErroresChat, MensajesLogChat, SystemPrompt

logger = logging.getLogger(__name__)

_settings = load_yaml_config('settings.yaml')
_llm_cfg = _settings.get('llm', {})

_LLM_BASE_URL = get_config('LLM_BASE_URL', '')
_LLM_API_KEY = get_config('LLM_API_KEY', '')
_LLM_MODEL = get_config('LLM_MODEL', _llm_cfg.get('default_model', 'gpt-4o-mini'))
_LLM_USER_EMAIL = get_config('LLM_USER_EMAIL', '')
_LLM_TIMEOUT = int(get_config('LLM_TIMEOUT', _llm_cfg.get('timeout_seconds', 90)))
_MAX_ITERATIONS = int(_llm_cfg.get('max_tool_iterations', 3))
_TEMPERATURE = float(_llm_cfg.get('temperature', 0.4))
_MAX_TOKENS = int(_llm_cfg.get('max_tokens', 1024))


def esta_configurado() -> bool:
    """Verifica si el LLM tiene credenciales configuradas."""
    resultado = bool(_LLM_BASE_URL and _LLM_API_KEY)
    return resultado


async def _fetch_context() -> str:
    """Obtiene los datos del sistema para inyectar en el prompt."""
    kpis, stats_facturas, stats_rechazos = await asyncio.gather(
        dashboard_service.obtener_kpis(),
        facturas_service.obtener_estadisticas(),
        rechazos_service.obtener_estadisticas(),
    )

    kpis_text = '\n'.join(
        f"  - {k['label']}: {k['value']}" for k in kpis
    )

    context = (
        f'\nDATOS EN TIEMPO REAL DEL SISTEMA (actualizados al momento de esta consulta):\n\n'
        f'Indicadores principales (KPIs):\n{kpis_text}\n\n'
        f'Estadísticas de facturas:\n'
        f'  - Total en BD: {stats_facturas["total"]}\n'
        f'  - Validadas: {stats_facturas["validadas"]}\n'
        f'  - Pendientes: {stats_facturas["pendientes"]}\n'
        f'  - Rechazadas: {stats_facturas["rechazadas"]}\n'
        f'  - Monto total procesado: ${stats_facturas["monto_total"]:,.0f} COP\n\n'
        f'Estadísticas de rechazos:\n'
        f'  - Rechazos hoy: {stats_rechazos["rechazos_hoy"]}\n'
        f'  - Severidad alta: {stats_rechazos["severidad_alta"]}\n'
        f'  - Reintentos: {stats_rechazos["reintentos"]}\n'
        f'  - Tasa de rechazo: {stats_rechazos["tasa_rechazo"]}%\n'
    )
    return context


async def construir_system_prompt() -> str:
    """Construye el system prompt completo con datos del sistema en tiempo real."""
    try:
        context = await cached('chat:context', _fetch_context, ttl=60)
    except Exception as e:
        logger.warning(MensajesLogChat.contexto_error, e)
        context = MensajesLogChat.contexto_fallback

    prompt_completo = SystemPrompt.base + context
    return prompt_completo


def _construir_url_llm() -> str:
    """Construye la URL completa del endpoint de chat completions."""
    base = _LLM_BASE_URL.rstrip('/')
    if not base.endswith('/v1'):
        base = f'{base}/v1'
    url = f'{base}/chat/completions'
    return url


def _construir_headers() -> dict:
    """Construye los headers para la petición al LLM."""
    headers = {
        'Authorization': f'Bearer {_LLM_API_KEY}',
        'Content-Type': 'application/json',
    }
    if _LLM_USER_EMAIL:
        headers['X-OpenWebUI-User-Email'] = _LLM_USER_EMAIL
    return headers


async def _ejecutar_tool_call(tool_call: dict) -> dict:
    """Ejecuta un tool call individual y retorna el mensaje de resultado.

    Args:
        tool_call: Diccionario con id, function.name y function.arguments.

    Returns:
        Diccionario con role='tool', tool_call_id y content.
    """
    fn_name = tool_call['function']['name']
    fn_args_raw = tool_call['function'].get('arguments', '{}')

    try:
        fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
    except json.JSONDecodeError:
        fn_args = {}

    logger.info(MensajesLogChat.tool_ejecutando, fn_name, fn_args)
    result = await chat_tools.execute_tool(fn_name, fn_args)

    mensaje_resultado = {
        'role': 'tool',
        'tool_call_id': tool_call['id'],
        'content': result,
    }
    return mensaje_resultado


async def procesar_chat(mensajes_usuario: list) -> str:
    """Procesa los mensajes del usuario y retorna la respuesta del LLM.

    Ejecuta el ciclo completo de function calling: envía mensajes al LLM,
    procesa tool calls si los hay, y retorna la respuesta final.

    Args:
        mensajes_usuario:
            Lista de dicts con role y content del historial del usuario.

    Returns:
        Texto de respuesta del asistente.

    Raises:
        httpx.TimeoutException: Si el LLM excede el timeout.
        httpx.RequestError: Si no se puede conectar al LLM.
        KeyError: Si la respuesta del LLM tiene formato inesperado.
    """
    system_prompt = await construir_system_prompt()
    messages_for_llm = [
        {'role': 'system', 'content': system_prompt},
        *mensajes_usuario,
    ]

    url = _construir_url_llm()
    headers = _construir_headers()

    async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
        for iteration in range(_MAX_ITERATIONS):
            payload = {
                'model': _LLM_MODEL,
                'messages': messages_for_llm,
                'temperature': _TEMPERATURE,
                'max_tokens': _MAX_TOKENS,
                'tools': chat_tools.TOOL_DEFINITIONS,
                'tool_choice': 'auto',
            }

            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                logger.error(
                    MensajesLogChat.llm_api_error,
                    response.status_code,
                    response.text[:500],
                )
                error_msg = ErroresChat.error_ia.format(status=response.status_code)
                raise httpx.HTTPStatusError(
                    error_msg, request=response.request, response=response,
                )

            data = response.json()
            message = data['choices'][0]['message']

            if not message.get('tool_calls'):
                answer = message.get('content', '')
                return answer

            logger.info(
                MensajesLogChat.tools_solicitadas,
                len(message['tool_calls']),
                iteration + 1,
            )

            messages_for_llm.append(message)

            for tool_call in message['tool_calls']:
                tool_result = await _ejecutar_tool_call(tool_call)
                messages_for_llm.append(tool_result)

        payload_final = {
            'model': _LLM_MODEL,
            'messages': messages_for_llm,
            'temperature': _TEMPERATURE,
            'max_tokens': _MAX_TOKENS,
        }
        response = await client.post(url, headers=headers, json=payload_final)
        data = response.json()
        answer = data['choices'][0]['message'].get('content', ErroresChat.fallback_sin_respuesta)

    return answer
