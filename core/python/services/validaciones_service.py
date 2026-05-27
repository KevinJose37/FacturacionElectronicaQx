"""Servicio de consultas para la página de reglas de validación."""

import logging
from datetime import datetime, timezone, timedelta

_TZ_BOGOTA = timezone(timedelta(hours=-5))

from config import load_yaml_queries
from core.python.db import get_pool
from metadata.validacion_metadata import ReglasValidacion

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('services/queries_services.yml').get('validaciones', {})


async def obtener_reglas_validacion(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Obtiene reglas de validación con conteo de resultados.

    Args:
        fecha_inicio: Fecha inicio en formato YYYY-MM-DD (opcional).
        fecha_fin: Fecha fin en formato YYYY-MM-DD (opcional).

    Returns:
        Lista de reglas con código, descripción, passed, failed y severidad.
    """
    pool = get_pool()
    
    if fecha_inicio and fecha_fin:
        query = _QUERIES['reglas_con_fechas']
        dt_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').replace(hour=0, minute=0, second=0, tzinfo=_TZ_BOGOTA)
        dt_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=_TZ_BOGOTA)
        params = (dt_inicio, dt_fin)
    else:
        query = _QUERIES['reglas']
        params = None

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            if params:
                await cur.execute(query, params)
            else:
                await cur.execute(query)
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        etapa = r[0]
        info = ReglasValidacion.mapa.get(etapa, (f'VAL-{etapa[:3]}', etapa, 'medium'))
        resultado.append({
            'code': info[0],
            'etapa': etapa,
            'rule': info[1],
            'passed': r[1],
            'failed': r[2],
            'severity': info[2],
        })
    return resultado


async def obtener_estadisticas(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> dict:
    """Calcula estadísticas agregadas de validaciones.

    Args:
        fecha_inicio: Fecha inicio en formato YYYY-MM-DD (opcional).
        fecha_fin: Fecha fin en formato YYYY-MM-DD (opcional).

    Returns:
        Diccionario con reglas_activas, total_passed, total_failed, tasa_exito.
    """
    reglas = await obtener_reglas_validacion(fecha_inicio, fecha_fin)
    total_passed = sum(r['passed'] for r in reglas)
    total_failed = sum(r['failed'] for r in reglas)
    total = total_passed + total_failed
    tasa = round((total_passed / max(total, 1)) * 100, 2)

    estadisticas = {
        'reglas_activas': len(reglas),
        'total_passed': total_passed,
        'total_failed': total_failed,
        'tasa_exito': tasa,
    }
    return estadisticas


async def obtener_facturas_fallidas(etapa: str, fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Obtiene las facturas que fallaron una regla específica.

    Args:
        etapa: Código de referencia de la etapa (ej: 'PARSEO').
        fecha_inicio: Fecha inicio en formato YYYY-MM-DD (opcional).
        fecha_fin: Fecha fin en formato YYYY-MM-DD (opcional).

    Returns:
        Lista de facturas con numero, proveedor, motivo, fecha y db_id.
    """
    pool = get_pool()

    if fecha_inicio and fecha_fin:
        dt_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').replace(hour=0, minute=0, second=0, tzinfo=_TZ_BOGOTA)
        dt_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=_TZ_BOGOTA)
    else:
        # Default to last 30 days
        dt_fin = datetime.now(tz=_TZ_BOGOTA)
        dt_inicio = dt_fin.replace(day=1)

    query = _QUERIES['facturas_por_regla']
    params = (etapa, dt_inicio, dt_fin)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        resultado.append({
            'numero_factura': r[0] or '—',
            'proveedor': r[1] or 'Sin nombre',
            'motivo_error': r[2] or 'Error no especificado',
            'fecha': r[3].strftime('%Y-%m-%d') if r[3] else '',
            'db_id': r[4],
        })
    return resultado


async def obtener_tendencia_7d() -> dict:
    """Obtiene la tendencia de pass/fail por regla de los últimos 7 días.

    Returns:
        Diccionario {etapa: [{dia, passed, failed}, ...]} para sparklines.
    """
    pool = get_pool()
    query = _QUERIES['tendencia_7d']

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query)
            filas = await cur.fetchall()

    tendencia: dict[str, list] = {}
    for r in filas:
        etapa = r[0]
        if etapa not in tendencia:
            tendencia[etapa] = []
        tendencia[etapa].append({
            'dia': r[1].strftime('%Y-%m-%d') if r[1] else '',
            'passed': r[2],
            'failed': r[3],
        })
    return tendencia
