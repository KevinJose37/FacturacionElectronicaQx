"""Servicio para auditoría de accesos y operaciones de Habeas Data."""

import json
from datetime import datetime, date
from typing import Any

from core.python.db import get_pool

async def registrar_auditoria(
    user_id: int,
    tipo_acceso: str,
    tabla_afectada: str,
    query_params: dict[str, Any] | None = None
) -> None:
    """Registra en base de datos una operación sensible realizada por un usuario.

    Args:
        user_id: ID del usuario que realiza la operación.
        tipo_acceso: Tipo de operación (ej. 'EXPORT_EXCEL', 'SUPRESION_DATOS').
        tabla_afectada: Entidad o tabla sobre la cual se operó.
        query_params: Parámetros del request (filtros, fechas, nits, etc.).
    """
    if query_params is None:
        query_params = {}

    # Sanitizar los parámetros para evitar errores de serialización JSON
    safe_params = {}
    for k, v in query_params.items():
        if isinstance(v, (datetime, date)):
            safe_params[k] = v.isoformat()
        else:
            safe_params[k] = str(v)

    pool = get_pool()
    query = """
        INSERT INTO FACTURACION.AUDITORIA_ACCESO 
        (ID_USUARIO, TIPO_ACCESO, TABLA_AFECTADA, QUERY_PARAMS)
        VALUES (%s, %s, %s, %s)
    """
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    query, 
                    [user_id, tipo_acceso, tabla_afectada, json.dumps(safe_params)]
                )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error al registrar auditoría de acceso: {e}")
