"""Puntos de entrada de la API para consultas de ingesta."""

import logging

from fastapi import APIRouter, Depends

from config import get_queries_ingesta
from core.python.db.connection import get_pool
from metadata.db_metadata import IdEstadoProceso
from core.python.auth.deps import get_current_active_user

router = APIRouter(tags=['ingesta'])

logger = logging.getLogger(__name__)


@router.get('/webhook/queue/status')
async def queue_status(current_user: dict = Depends(get_current_active_user)) -> dict:
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
