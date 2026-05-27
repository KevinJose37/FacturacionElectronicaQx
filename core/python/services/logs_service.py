"""Servicio de consultas para la página de logs."""

import logging
import re
from datetime import datetime, timezone, timedelta

from config import load_yaml_queries
from core.python.db import get_pool
from metadata.common_metadata import DefaultTextos
from metadata.log_service_metadata import MensajesLog

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('services/queries_services.yml').get('logs', {})
_FILTROS = load_yaml_queries('services/queries_services.yml').get('logs_filtros', {})


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
    inicio = datetime.now(tz=timezone.utc) - timedelta(days=30)
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


async def obtener_trail(termino: str) -> dict:
    """Obtiene el trail completo de procesamiento para una factura o correo.

    Busca por número de factura, remitente o asunto, y retorna todos los
    pasos del pipeline asociados, agrupados por correo.

    Args:
        termino: Texto de búsqueda (nº factura, email o asunto).

    Returns:
        Diccionario con la lista de trails agrupados por correo y el conteo total.
    """
    pool = get_pool()
    patron = f'%{termino}%'

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['trail'], (patron, patron, patron))
            filas = await cur.fetchall()

    if not filas:
        return {'trails': [], 'total': 0}

    # Agrupar por correo_id
    trails_dict = {}
    for r in filas:
        # r[0]=fecha_inicio, r[1]=fecha_fin, r[2]=etapa, r[3]=etapa_codigo,
        # r[4]=estado_codigo, r[5]=detalle_error, r[6]=observacion,
        # r[7]=numero_factura, r[8]=correo_id, r[9]=remitente,
        # r[10]=asunto, r[11]=fecha_deteccion, r[12]=nombre_archivo, r[13]=adjunto_id
        
        correo_id = r[8]
        if correo_id not in trails_dict:
            correo_info = {
                'correo_id': correo_id,
                'remitente': r[9] or '',
                'asunto': r[10] or '',
                'fecha_deteccion': r[11].strftime('%d/%m/%Y %H:%M') if r[11] else '',
            }
            trails_dict[correo_id] = {
                'correo': correo_info,
                'steps': []
            }

        ts_inicio = r[0].strftime(DefaultTextos.formato_hora) if r[0] else ''
        ts_fin = r[1].strftime(DefaultTextos.formato_hora) if r[1] else ''
        duracion_ms = None
        if r[0] and r[1]:
            duracion_ms = int((r[1] - r[0]).total_seconds() * 1000)

        status = 'ok'
        if r[5]:  # tiene error
            status = 'error'
        elif r[4] in ('ERROR', 'FALLIDO'):
            status = 'error'
        elif r[4] == 'EN_PROCESO':
            status = 'running'
        elif r[4] == 'PENDIENTE':
            status = 'pending'

        trails_dict[correo_id]['steps'].append({
            'ts': ts_inicio,
            'ts_fin': ts_fin,
            'duracion_ms': duracion_ms,
            'etapa': r[2] or '',
            'etapa_codigo': r[3] or '',
            'status': status,
            'error': r[5] or '',
            'observacion': r[6] or '',
            'numero_factura': r[7] or '',
            'nombre_archivo': r[12] or '',
            'adjunto_id': r[13],
        })

    # Convertir dict a lista
    trails_list = list(trails_dict.values())
    
    # Ordenar los grupos por la fecha del primer paso de cada grupo (para que queden cronológicamente ordenados)
    trails_list.sort(key=lambda t: t['steps'][0]['ts'] if t['steps'] else '', reverse=True)

    return {
        'trails': trails_list,
        'total': len(filas)
    }
