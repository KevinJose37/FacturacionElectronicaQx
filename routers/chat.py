"""Endpoint del chatbot Innti — Asistente inteligente de QUIPUX.

Conecta al LLM vía API compatible con OpenAI, inyectando datos
reales del sistema de facturación en el system prompt para que
el asistente pueda responder consultas con información actualizada.
"""

import asyncio
import json
import logging
import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core import dashboard_service, facturas_service, rechazos_service, chat_tools
from core.cache import cached

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/chat', tags=['chat'])

# ── Config LLM ──────────────────────────────────────────────────────
LLM_BASE_URL = os.environ.get('LLM_BASE_URL', '')
LLM_API_KEY = os.environ.get('LLM_API_KEY', '')
LLM_MODEL = os.environ.get('LLM_MODEL', 'gpt-4o-mini')
LLM_USER_EMAIL = os.environ.get('LLM_USER_EMAIL', '')
LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '45'))


# ── Schemas ─────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str       # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    role: str
    content: str


# ── System Prompt ───────────────────────────────────────────────────
SYSTEM_PROMPT_BASE = """Eres **Innti**, el asistente inteligente de **QUIPUX Director Apolo**, \
un sistema de facturación electrónica colombiana.

Tu rol:
- Ayudar al usuario a entender el estado del sistema de facturación.
- Responder preguntas sobre facturas, proveedores, validaciones, rechazos y logs.
- Ser conciso, profesional y amigable. Responde siempre en español.
- Usa datos reales del sistema que se te proporcionan abajo.
- Si no tienes datos suficientes para una pregunta específica, indícalo claramente.
- No inventes datos. Si el dato no está en el contexto proporcionado, di que no lo tienes disponible.
- Puedes formatear tus respuestas con markdown básico (negritas, listas, etc).

Contexto del sistema:
- El sistema procesa facturas electrónicas colombianas (FE, NC, ND, DS).
- Las facturas pasan por un pipeline: Recepción → Verificación → Escaneo → Parsing XML → Validación DIAN → Persistencia.
- Los estados posibles son: pendiente, validada, rechazada, error.
- Los rechazos pueden ser por CUFE inválido, NIT no registrado, XML mal formado, etc.
"""


async def _build_system_context() -> str:
    """Construye el contexto del sistema consultando la BD en tiempo real.

    Reutiliza las funciones de servicio existentes para obtener datos
    actualizados sin duplicar lógica de queries.
    """
    try:
        # Usar cache para no re-consultar la BD en cada mensaje
        dashboard = await cached('chat:context', _fetch_context, ttl=60)
        return dashboard
    except Exception as e:
        logger.warning('Error obteniendo contexto para chat: %s', e)
        return '\n[No se pudieron obtener datos del sistema en este momento.]\n'


async def _fetch_context() -> str:
    """Obtiene los datos del sistema para inyectar en el prompt."""

    kpis, stats_facturas, stats_rechazos = await asyncio.gather(
        dashboard_service.obtener_kpis(),
        facturas_service.obtener_estadisticas(),
        rechazos_service.obtener_estadisticas(),
    )

    # Formatear datos de KPIs
    kpis_text = '\n'.join(
        f"  - {k['label']}: {k['value']}" for k in kpis
    )

    context = f"""
DATOS EN TIEMPO REAL DEL SISTEMA (actualizados al momento de esta consulta):

Indicadores principales (KPIs):
{kpis_text}

Estadísticas de facturas:
  - Total en BD: {stats_facturas['total']}
  - Validadas: {stats_facturas['validadas']}
  - Pendientes: {stats_facturas['pendientes']}
  - Rechazadas: {stats_facturas['rechazadas']}
  - Monto total procesado: ${stats_facturas['monto_total']:,.0f} COP

Estadísticas de rechazos:
  - Rechazos hoy: {stats_rechazos['rechazos_hoy']}
  - Severidad alta: {stats_rechazos['severidad_alta']}
  - Reintentos: {stats_rechazos['reintentos']}
  - Tasa de rechazo: {stats_rechazos['tasa_rechazo']}%
"""
    return context


# ── Endpoint ────────────────────────────────────────────────────────
@router.post('', response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Procesa un mensaje del usuario y devuelve la respuesta del LLM.

    Soporta function calling: el LLM puede invocar herramientas para
    consultar la BD cuando necesite datos específicos.
    """
    if not LLM_BASE_URL or not LLM_API_KEY:
        raise HTTPException(
            status_code=503,
            detail='Chatbot no configurado. Faltan LLM_BASE_URL y/o LLM_API_KEY en .env',
        )

    # Construir system prompt con datos reales (KPIs generales)
    context = await _build_system_context()
    full_system = SYSTEM_PROMPT_BASE + context

    # Preparar mensajes para el LLM
    messages_for_llm = [
        {'role': 'system', 'content': full_system},
        *[{'role': m.role, 'content': m.content} for m in req.messages],
    ]

    # Headers y URL
    headers = {
        'Authorization': f'Bearer {LLM_API_KEY}',
        'Content-Type': 'application/json',
    }
    if LLM_USER_EMAIL:
        headers['X-OpenWebUI-User-Email'] = LLM_USER_EMAIL

    base = LLM_BASE_URL.rstrip('/')
    if not base.endswith('/v1'):
        base = f'{base}/v1'
    url = f'{base}/chat/completions'

    # Máximo 3 iteraciones de tool calling para evitar loops infinitos
    max_iterations = 3

    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
            for iteration in range(max_iterations):
                payload = {
                    'model': LLM_MODEL,
                    'messages': messages_for_llm,
                    'temperature': 0.4,
                    'max_tokens': 1024,
                    'tools': chat_tools.TOOL_DEFINITIONS,
                    'tool_choice': 'auto',
                }

                response = await client.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    logger.error(
                        'LLM API error: status=%d body=%s',
                        response.status_code,
                        response.text[:500],
                    )
                    raise HTTPException(
                        status_code=502,
                        detail=f'Error del servicio de IA (status {response.status_code})',
                    )

                data = response.json()
                choice = data['choices'][0]
                message = choice['message']

                # Si el LLM NO pidió tools, devolver la respuesta directa
                if not message.get('tool_calls'):
                    answer = message.get('content', '')
                    return ChatResponse(role='assistant', content=answer)

                # El LLM pidió ejecutar tools — procesarlas
                logger.info(
                    'LLM solicitó %d tool(s) en iteración %d',
                    len(message['tool_calls']),
                    iteration + 1,
                )

                # Agregar el mensaje del asistente con tool_calls al historial
                messages_for_llm.append(message)

                # Ejecutar cada tool y agregar resultados
                for tool_call in message['tool_calls']:
                    fn_name = tool_call['function']['name']
                    fn_args_raw = tool_call['function'].get('arguments', '{}')

                    try:
                        fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                    except json.JSONDecodeError:
                        fn_args = {}

                    logger.info('Ejecutando tool: %s(%s)', fn_name, fn_args)
                    result = await chat_tools.execute_tool(fn_name, fn_args)

                    # Agregar resultado al historial
                    messages_for_llm.append({
                        'role': 'tool',
                        'tool_call_id': tool_call['id'],
                        'content': result,
                    })

            # Si llegamos aquí, se agotaron las iteraciones
            # Hacer una última llamada SIN tools para forzar una respuesta
            payload_final = {
                'model': LLM_MODEL,
                'messages': messages_for_llm,
                'temperature': 0.4,
                'max_tokens': 1024,
            }
            response = await client.post(url, headers=headers, json=payload_final)
            data = response.json()
            answer = data['choices'][0]['message'].get('content', 'No pude procesar tu consulta.')
            return ChatResponse(role='assistant', content=answer)

    except httpx.TimeoutException:
        logger.error('LLM API timeout after %ds', LLM_TIMEOUT)
        raise HTTPException(
            status_code=504,
            detail='El servicio de IA tardó demasiado en responder. Intenta de nuevo.',
        )
    except httpx.RequestError as e:
        logger.error('LLM API connection error: %s', e)
        raise HTTPException(
            status_code=502,
            detail='No se pudo conectar con el servicio de IA.',
        )
    except (KeyError, IndexError) as e:
        logger.error('LLM API unexpected response format: %s', e)
        raise HTTPException(
            status_code=502,
            detail='Respuesta inesperada del servicio de IA.',
        )
