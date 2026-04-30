"""Servicio de consultas para la página de rechazos."""

import logging
from datetime import datetime, timezone

from core.db import get_pool

logger = logging.getLogger(__name__)


async def listar_rechazos() -> list:
    """Lista facturas rechazadas con detalles del error.

    Returns:
        Lista de rechazos con proveedor, razón y severidad.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT f.prefijo_facturacion || \'-\' || f.numero_factura as num, '
                't.nombre_comercial, '
                'vd.descripcion_respuesta, '
                'vd.codigo_respuesta, '
                'vd.fecha_validacion, '
                'f.id_estado_proceso '
                'FROM facturacion.factura f '
                'JOIN facturacion.tercero t ON f.id_tercero_emisor = t.id_tercero '
                'LEFT JOIN facturacion.validacion_dian vd ON f.id_factura = vd.id_factura '
                'WHERE f.id_estado_proceso IN (8, 10) '
                'ORDER BY vd.fecha_validacion DESC NULLS LAST'
            )
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        severidad = 'high' if r[5] == 10 else 'medium'
        resultado.append({
            'id': r[0],
            'provider': r[1] or 'Sin nombre',
            'reason': r[2] or 'Error no especificado',
            'rule': r[3] or 'ERR-GEN',
            'date': r[4].strftime('%d/%m %H:%M') if r[4] else '',
            'severity': severidad,
        })
    return resultado


async def obtener_estadisticas() -> dict:
    """Calcula estadísticas de rechazos.

    Returns:
        Diccionario con rechazos hoy, severidad alta, reintentos y tasa.
    """
    pool = get_pool()
    ahora = datetime.now(tz=timezone.utc)
    inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura '
                'WHERE id_estado_proceso IN (8, 10) AND fecha_creacion >= %s',
                (inicio_hoy,),
            )
            rechazos_hoy = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso = 10'
            )
            severidad_alta = (await cur.fetchone())[0]

            await cur.execute('SELECT COUNT(*) FROM facturacion.factura')
            total = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.proceso_ingesta '
                'WHERE id_estado_proceso IN (8, 10)'
            )
            reintentos = (await cur.fetchone())[0]

    rechazos_total = rechazos_hoy
    tasa = round((rechazos_total / max(total, 1)) * 100, 1)

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
        Lista de causas con conteo, ordenada por frecuencia.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT vd.codigo_respuesta, COUNT(*) as total '
                'FROM facturacion.validacion_dian vd '
                'WHERE vd.id_estado_proceso IN (8, 10) '
                'GROUP BY vd.codigo_respuesta '
                'ORDER BY total DESC'
            )
            filas = await cur.fetchall()

    resultado = [{'rule': r[0] or 'ERR-GEN', 'count': r[1]} for r in filas]
    return resultado
