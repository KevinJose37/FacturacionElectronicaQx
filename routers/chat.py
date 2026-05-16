"""Endpoint del chatbot Innti — Asistente inteligente de QUIPUX.

Router delgado que delega toda la lógica al servicio en
``core.python.chat.service``.
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.python.chat import service as chat_service
from metadata.chat_metadata import ErroresChat, MensajesLogChat

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/chat', tags=['chat'])


class ChatMessage(BaseModel):
    """Mensaje individual del historial de chat."""

    role: str
    content: str


from typing import List

class ChatRequest(BaseModel):
    """Request con el historial de mensajes del usuario."""

    messages: List[ChatMessage]


class ChatResponse(BaseModel):
    """Respuesta del asistente."""

    role: str
    content: str


@router.post('', response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    """Procesa un mensaje del usuario y devuelve la respuesta del LLM.

    Soporta function calling: el LLM puede invocar herramientas para
    consultar la BD cuando necesite datos específicos.
    """
    if not chat_service.esta_configurado():
        raise HTTPException(status_code=503, detail=ErroresChat.no_configurado)

    mensajes = [{'role': m.role, 'content': m.content} for m in req.messages]

    try:
        respuesta_texto = await chat_service.procesar_chat(mensajes)
    except httpx.TimeoutException:
        logger.error(MensajesLogChat.llm_timeout, chat_service._LLM_TIMEOUT)
        raise HTTPException(status_code=504, detail=ErroresChat.timeout_ia)
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=502, detail=ErroresChat.respuesta_inesperada)
    except httpx.RequestError as e:
        logger.error(MensajesLogChat.llm_conexion_error, e)
        raise HTTPException(status_code=502, detail=ErroresChat.conexion_ia)
    except (KeyError, IndexError) as e:
        logger.error(MensajesLogChat.llm_formato_error, e)
        raise HTTPException(status_code=502, detail=ErroresChat.respuesta_inesperada)

    respuesta = ChatResponse(role='assistant', content=respuesta_texto)
    return respuesta
