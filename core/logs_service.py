"""Servicio de consultas para la página de logs."""

import logging
from datetime import datetime, timezone

from core.db import get_pool

logger = logging.getLogger(__name__)

MAPA_NIVEL = {
    'info': ['RECEPCION', 'PERSISTENCIA', 'EXTRACCION_XML'],
    'warn': ['VERIFICACION_ADJUNTO'],
    'error': [],
}


async def listar_logs(nivel: str | None = None, busqueda: str | None = None, limite: int = 50) -> list:
    """Lista logs del sistema con filtros opcionales.

    Args:
        nivel: Filtro por nivel (info, warn, error, debug).
        busqueda: Texto libre para buscar en mensajes.
        limite: Cantidad máxima de registros.

    Returns:
        Lista de entradas de log.
    """
    pool = get_pool()
    condiciones = []
    params = []

    if nivel == 'error':
        condiciones.append('lp.detalle_error IS NOT NULL')
    elif nivel == 'warn':
        condiciones.append("lp.detalle_json::text ILIKE '%warn%'")
    elif nivel == 'info':
        condiciones.append('lp.detalle_error IS NULL')

    if busqueda:
        condiciones.append(
            '(lp.codigo_etapa ILIKE %s OR lp.detalle_error ILIKE %s)'
        )
        patron = f'%{busqueda}%'
        params.extend([patron, patron])

    where = f'WHERE {" AND ".join(condiciones)}' if condiciones else ''

    query = (
        f'SELECT lp.fecha_inicio, lp.codigo_etapa, lp.detalle_error, '
        f'lp.detalle_json '
        f'FROM facturacion.log_proceso lp '
        f'{where} '
        f'ORDER BY lp.fecha_inicio DESC LIMIT %s'
    )
    params.append(limite)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        fecha = r[0]
        ts = fecha.strftime('%H:%M:%S') if fecha else ''

        if r[2]:
            nivel_log = 'error'
            msg = f'{r[1]} · {r[2][:120]}'
        else:
            detalle = r[3] if r[3] else {}
            nivel_raw = detalle.get('nivel', 'info') if isinstance(detalle, dict) else 'info'
            nivel_log = nivel_raw
            msg = f'{r[1]} completado correctamente'

        fuente = 'pipeline'
        if isinstance(r[3], dict):
            fuente = r[3].get('fuente', 'pipeline')

        resultado.append({
            'ts': ts,
            'level': nivel_log,
            'source': fuente,
            'msg': msg,
        })
    return resultado


async def obtener_conteos() -> dict:
    """Calcula conteos de logs por nivel en las últimas 24h.

    Returns:
        Diccionario con total_24h, info, warn, error.
    """
    pool = get_pool()
    inicio = datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.log_proceso WHERE fecha_inicio >= %s',
                (inicio,),
            )
            total = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.log_proceso '
                'WHERE fecha_inicio >= %s AND detalle_error IS NOT NULL',
                (inicio,),
            )
            errores = (await cur.fetchone())[0]

            await cur.execute(
                "SELECT COUNT(*) FROM facturacion.log_proceso "
                "WHERE fecha_inicio >= %s AND detalle_json::text ILIKE '%%warn%%'",
                (inicio,),
            )
            warnings = (await cur.fetchone())[0]

    conteos = {
        'total_24h': total,
        'info': total - errores - warnings,
        'warn': warnings,
        'error': errores,
    }
    return conteos
