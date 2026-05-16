"""Puntos de entrada de la API para disparar procesos de ingesta."""

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from config import get_config, get_queries_ingesta
from core import EmailListener
from core.python.db.connection import get_pool
from metadata.db_metadata import IdEstadoProceso

router = APIRouter(tags=['webhook'])

logger = logging.getLogger(__name__)

_WEBHOOK_SECRET = get_config('WEBHOOK_SECRET', '')


def _run_ingesta() -> None:
    """Ejecuta el listener de correos. Los workers procesan las facturas."""
    try:
        EmailListener().run()
        logger.info('Ingesta completada. Workers procesarán los eventos pendientes.')
    except Exception as e:
        logger.exception('Falla crítica en background task de ingesta: %s', e)


@router.post('/webhook/gmail')
@router.post('/api/webhook/')
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
    logger.info('Webhook de Gmail invocado. Validando secreto...')
    if not _WEBHOOK_SECRET or x_webhook_secret != _WEBHOOK_SECRET:
        logger.warning('Webhook rechazado: Secreto inválido o no configurado.')
        raise HTTPException(status_code=403, detail='Unauthorized')

    logger.info('Secreto validado. Encolando _run_ingesta en BackgroundTasks...')
    background_tasks.add_task(_run_ingesta)
    logger.info('Tarea encolada. Retornando 200 OK.')
    respuesta = {'status': 'accepted'}
    return respuesta


@router.get('/webhook/queue/status')
async def queue_status() -> dict:
    """Retorna el estado actual de la cola de trabajo."""
    pool = get_pool()
    queries = get_queries_ingesta()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(queries['estado_cola'], (IdEstadoProceso.pendiente, IdEstadoProceso.en_proceso, IdEstadoProceso.procesado, IdEstadoProceso.fallido, IdEstadoProceso.en_proceso))
                row = await cur.fetchone()
                
        return {
            'pendientes': row[0] or 0,
            'en_proceso': row[1] or 0,
            'procesados_ultima_hora': row[2] or 0,
            'fallidos': row[3] or 0,
            'workers_activos': row[4] or []
        }
    except Exception as e:
        logger.error('Error consultando estado de la cola: %s', e)
        return {'status': 'error'}

