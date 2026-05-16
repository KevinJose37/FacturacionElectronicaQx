"""Servicio de monitoreo del estado de la aplicación (Healthcheck)."""

import logging
from datetime import datetime, timezone

from core.python.db import get_pool

logger = logging.getLogger(__name__)


async def get_health_status() -> dict:
    """Valida el estado de los componentes del sistema.

    Returns:
        Diccionario con el estado global, servicios individuales y timestamp.
    """
    db_status = "down"
    global_status = "error"
    
    try:
        pool = get_pool()
        if pool:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    result = await cur.fetchone()
                    if result and result[0] == 1:
                        db_status = "up"
                        global_status = "ok"
    except Exception as e:
        logger.error(f"Error en healthcheck de base de datos: {e}")

    return {
        "status": global_status,
        "services": {
            "database": db_status
        },
        "timestamp": datetime.now(tz=timezone.utc).isoformat()
    }
