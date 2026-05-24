"""Servicio de monitoreo del estado de la aplicación (Healthcheck)."""

import logging
from datetime import datetime, timezone

import httpx
from core.python.db import get_pool
from core.python.chat import service as chat_service

logger = logging.getLogger(__name__)


async def get_health_status() -> dict:
    """Valida el estado de los componentes del sistema.

    Returns:
        Diccionario con el estado global, servicios individuales y timestamp.
    """
    db_status = "down"
    llm_status = "down"
    global_status = "error"
    
    # 1. Check DB
    try:
        pool = get_pool()
        if pool:
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    result = await cur.fetchone()
                    if result and result[0] == 1:
                        db_status = "up"
    except Exception as e:
        logger.error(f"Error en healthcheck de base de datos: {e}")

    # 2. Check LLM
    try:
        if chat_service.esta_configurado():
            base_url = chat_service._LLM_BASE_URL.rstrip('/')
            if not base_url.endswith('/v1'):
                base_url = f'{base_url}/v1'
            
            # Intentar un GET rápido a /models (estándar OpenAI)
            headers = chat_service._construir_headers()
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.get(f'{base_url}/models', headers=headers)
                    if res.status_code == 200:
                        llm_status = "up"
            except Exception as ssl_err:
                logger.warning(f"Healthcheck de LLM con verificación SSL falló ({ssl_err}), reintentando sin verificar SSL...")
                try:
                    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                        res = await client.get(f'{base_url}/models', headers=headers)
                        if res.status_code == 200:
                            llm_status = "up"
                except Exception as retry_err:
                    logger.error(f"Reintento de healthcheck de LLM sin verificación SSL también falló: {retry_err}")
        else:
            logger.warning("LLM no configurado, omitiendo healthcheck profundo.")
    except Exception as e:
        logger.error(f"Error en healthcheck de LLM: {e}")

    if db_status == "up":
        # Si la base de datos está activa (corazón del sistema de facturación), el estado es estable (ok).
        # Si el LLM opcional está caído o simplemente no está configurado, el sistema sigue operativo.
        if llm_status == "up" or not chat_service.esta_configurado():
            global_status = "ok"
        else:
            global_status = "degraded"

    return {
        "status": global_status,
        "services": {
            "database": db_status,
            "llm_api": llm_status
        },
        "timestamp": datetime.now(tz=timezone.utc).isoformat()
    }
