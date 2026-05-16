"""Servicio de consultas para la página de logs."""

import logging
import re
from datetime import datetime, timezone

from config import get_queries_services
from core.python.db import get_pool
from metadata.common_metadata import DefaultTextos
from metadata.log_service_metadata import MensajesLog

logger = logging.getLogger(__name__)

_QUERIES = get_queries_services().get('logs', {})
_FILTROS = get_queries_services().get('logs_filtros', {})


async def listar_logs(
    nivel: str | None = None,
    busqueda: str | None = None,
    limite: int = 50,
) -> list:
    """Lista logs del sistema con filtros opcionales.

    Args:
        nivel: Filtro por nivel (error, warn, info).
        busqueda: Texto libre para buscar en etapa o error.
        limite: Máximo de logs a retornar.

    Returns:
        Lista de logs con timestamp, nivel, fuente y mensaje.
    """
    pool = get_pool()
    condiciones = []
    params = []

    if nivel and nivel in _FILTROS:
        condiciones.append(_FILTROS[nivel])

    if busqueda:
        condiciones.append(_FILTROS['busqueda'])
        patron = f'%{busqueda}%'
        params.extend([patron, patron])

    where = f'WHERE {" AND ".join(condiciones)}' if condiciones else ''
    query = _QUERIES['listar'].format(where=where)
    params.append(limite)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        # r[0]=fecha_inicio, r[1]=etapa, r[2]=detalle_error, r[3]=observacion,
        # r[4]=num_factura, r[5]=remitente, r[6]=asunto
        fecha = r[0]
        ts = fecha.strftime(DefaultTextos.formato_hora) if fecha else ''
        num_factura = r[4]
        remitente = r[5]
        asunto = r[6]

        if r[2]:
            nivel_log = MensajesLog.nivel_error
            msg_base = MensajesLog.error_prefijo.format(etapa=r[1], detalle=r[2][:120])
        else:
            nivel_log = MensajesLog.nivel_default
            msg_base = MensajesLog.completado.format(etapa=r[1])

        # Lógica de construcción del mensaje final
        msg_final = msg_base
        
        # Determinar fuente y limpiar mensaje
        if r[2]:  # Es un error
            fuente = ""
        elif num_factura:  # No es error y tiene factura
            fuente = num_factura
        else:  # No es error y no tiene factura
            fuente = ""

        if remitente and 'Evaluación de correo' in msg_base:
            # Limpiar remitente
            match_email = re.search(r'[\w\.-]+@[\w\.-]+', remitente)
            email_limpio = match_email.group(0) if match_email else remitente
            asunto_txt = asunto or 'Sin Asunto'
            msg_final = f'Asunto: "{asunto_txt}" de {email_limpio} · {msg_base}'

        resultado.append({'ts': ts, 'level': nivel_log, 'source': fuente, 'msg': msg_final})

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
            await cur.execute(_QUERIES['conteos'], (inicio,))
            row = await cur.fetchone()
            total, errores, warnings = row[0], row[1], row[2]

    conteos = {
        'total_24h': total,
        'info': total - errores - warnings,
        'warn': warnings,
        'error': errores,
    }
    return conteos
