"""Puntos de entrada de la API para disparar procesos de ingesta."""

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from config import get_config
from core import EmailListener

router = APIRouter(prefix='/webhook', tags=['webhook'])

logger = logging.getLogger(__name__)

_WEBHOOK_SECRET = get_config('WEBHOOK_SECRET', '')


def _run_ingesta() -> None:
    """Ejecuta el listener de correos de forma síncrona para background tasks."""
    try:
        EmailListener().run()
    except Exception as e:
        logger.error('Falla en background task: %s', e)


@router.post('/gmail')
async def gmail_webhook(
    background_tasks: BackgroundTasks,
    x_webhook_secret: str = Header(None),
) -> dict:
    """Recibe notificaciones de Gmail e inicia la ingesta.

    Args:
        background_tasks: Gestor de tareas en segundo plano.
        x_webhook_secret: Token de validación (Header).

    Raises:
        HTTPException: Si el secreto es inválido o no está configurado.
    """
    if not _WEBHOOK_SECRET or x_webhook_secret != _WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail='Unauthorized')

    background_tasks.add_task(_run_ingesta)
    respuesta = {'status': 'accepted'}
    return respuesta
