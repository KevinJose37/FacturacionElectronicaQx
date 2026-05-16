"""Servicio de consultas para la página de rechazos."""

import logging
from datetime import datetime, timezone

from config import load_yaml_queries
from core.python.db import get_pool
from metadata.common_metadata import DefaultTextos

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('services/queries_services.yml').get('rechazos', {})


async def listar_rechazos() -> list:
    """Lista facturas rechazadas con detalles del error.

    Returns:
        Lista de rechazos con proveedor, motivo, regla y severidad.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['listar'])
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        # r[5]=id_estado_proceso: 5=FALLIDO → high, 4=ERROR → medium
        severidad = 'high' if r[5] == 5 else 'medium'
        resultado.append({
            'id': r[0],
            'provider': r[1] or DefaultTextos.sin_nombre,
            'reason': r[2] or DefaultTextos.error_no_especificado,
            'rule': r[3] or DefaultTextos.error_generico_regla,
            'date': r[4].strftime(DefaultTextos.formato_fecha_corto) if r[4] else '',
            'severity': severidad,
        })
    return resultado


async def obtener_estadisticas() -> dict:
    """Calcula estadísticas de rechazos.

    Returns:
        Diccionario con rechazos_hoy, severidad_alta, reintentos, tasa_rechazo.
    """
    pool = get_pool()
    ahora = datetime.now(tz=timezone.utc)
    inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['estadisticas'], (inicio_hoy,))
            row = await cur.fetchone()
            rechazos_hoy, severidad_alta, total = row[0], row[1], row[2]

            await cur.execute(_QUERIES['reintentos'])
            reintentos = (await cur.fetchone())[0]

    tasa = round((rechazos_hoy / max(total, 1)) * 100, 1)
    estadisticas = {
        'rechazos_hoy': rechazos_hoy,
        'severidad_alta': severidad_alta,
        'reintentos': reintentos,
        'tasa_rechazo': tasa,
    }
    return estadisticas


async def obtener_causas_frecuentes() -> list:
    """Agrupa rechazos por código de respuesta.

    Returns:
        Lista de causas con código y conteo.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['causas_frecuentes'])
            filas = await cur.fetchall()

    resultado = [
        {'rule': r[0] or DefaultTextos.error_generico_regla, 'count': r[1]}
        for r in filas
    ]
    return resultado
