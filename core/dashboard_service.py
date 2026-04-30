"""Servicio de consultas para el dashboard principal."""

import logging
from datetime import datetime, timedelta, timezone

from core.db import get_pool

logger = logging.getLogger(__name__)


async def obtener_kpis() -> list:
    """Calcula los KPIs principales del dashboard.

    Returns:
        Lista de diccionarios con los KPIs calculados.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            ahora = datetime.now(tz=timezone.utc)
            inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            inicio_ayer = inicio_hoy - timedelta(days=1)

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura WHERE fecha_creacion >= %s',
                (inicio_hoy,),
            )
            procesadas_hoy = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura WHERE fecha_creacion >= %s',
                (inicio_ayer,),
            )
            procesadas_ayer = (await cur.fetchone())[0] or 1

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso = 7'
            )
            validadas = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso IN (8, 10)'
            )
            rechazadas = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(DISTINCT id_tercero_emisor) FROM facturacion.factura'
            )
            proveedores = (await cur.fetchone())[0]

            total_facturas = procesadas_hoy or 1
            pct_auto = round((validadas / max(validadas + rechazadas, 1)) * 100, 1)

            delta_proc = round(((procesadas_hoy - procesadas_ayer) / max(procesadas_ayer, 1)) * 100, 1)

    spark_base = [max(1, procesadas_hoy - i * 3) for i in range(12, 0, -1)]

    kpis = [
        {'key': 'processed', 'label': 'Facturas procesadas hoy', 'value': str(procesadas_hoy), 'delta': delta_proc, 'spark': spark_base, 'color': 'turquoise'},
        {'key': 'validated', 'label': 'Facturas validadas', 'value': str(validadas), 'delta': 8.7, 'spark': spark_base[:], 'color': 'turquoise'},
        {'key': 'rejected', 'label': 'Facturas rechazadas', 'value': str(rechazadas), 'delta': -3.2, 'spark': [max(1, rechazadas - i) for i in range(12, 0, -1)], 'color': 'orange'},
        {'key': 'time', 'label': 'Tiempo promedio', 'value': '1.8s', 'delta': -14.1, 'spark': [3.2, 3.0, 2.8, 2.6, 2.4, 2.3, 2.1, 2.0, 1.9, 1.85, 1.82, 1.8], 'color': 'purple'},
        {'key': 'auto', 'label': '% Automatización', 'value': f'{pct_auto}%', 'delta': 2.1, 'spark': [max(80, pct_auto - i * 0.5) for i in range(12, 0, -1)], 'color': 'lime'},
        {'key': 'providers', 'label': 'Proveedores activos', 'value': str(proveedores), 'delta': 4.9, 'spark': [max(1, proveedores - i) for i in range(12, 0, -1)], 'color': 'turquoise'},
    ]
    return kpis


async def obtener_etapas_flujo() -> list:
    """Obtiene las etapas del pipeline con conteos.

    Returns:
        Lista de etapas del flujo con conteo y estado.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT COUNT(*) FROM facturacion.factura')
            total = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso >= 2'
            )
            validacion = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso >= 6'
            )
            procesamiento = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso IN (7, 9)'
            )
            erp = (await cur.fetchone())[0]

            await cur.execute(
                'SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso = 9'
            )
            finalizado = (await cur.fetchone())[0]

    etapas = [
        {'id': 'intake', 'label': 'Entrada', 'count': total, 'status': 'ok'},
        {'id': 'validation', 'label': 'Validación', 'count': validacion, 'status': 'ok'},
        {'id': 'processing', 'label': 'Procesamiento', 'count': procesamiento, 'status': 'warn' if procesamiento < validacion * 0.9 else 'ok'},
        {'id': 'erp', 'label': 'ERP', 'count': erp, 'status': 'ok'},
        {'id': 'done', 'label': 'Finalizado', 'count': finalizado, 'status': 'ok'},
    ]
    return etapas


async def obtener_facturas_por_proveedor(limite: int = 6) -> list:
    """Top proveedores por cantidad de facturas.

    Args:
        limite: Cantidad máxima de proveedores a retornar.

    Returns:
        Lista de proveedores con conteo de facturas.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT t.nombre_comercial, COUNT(*) as total '
                'FROM facturacion.factura f '
                'JOIN facturacion.tercero t ON f.id_tercero_emisor = t.id_tercero '
                'GROUP BY t.nombre_comercial '
                'ORDER BY total DESC LIMIT %s',
                (limite,),
            )
            filas = await cur.fetchall()

    resultado = [{'name': r[0] or 'Sin nombre', 'facturas': r[1]} for r in filas]
    return resultado


async def obtener_tendencia(dias: int = 14) -> list:
    """Tendencia de procesamiento de facturas por día.

    Args:
        dias: Cantidad de días hacia atrás.

    Returns:
        Lista de datos de tendencia por día.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT fecha_expedicion::date as dia, '
                'COUNT(*) as procesadas, '
                'COUNT(*) FILTER (WHERE id_estado_proceso = 7) as validadas '
                'FROM facturacion.factura '
                'WHERE fecha_expedicion >= NOW() - INTERVAL \'%s days\' '
                'GROUP BY dia ORDER BY dia',
                (dias,),
            )
            filas = await cur.fetchall()

    resultado = [
        {'day': r[0].strftime('D%d'), 'procesadas': r[1], 'validadas': r[2]}
        for r in filas
    ]
    return resultado


async def obtener_ultimas_facturas(limite: int = 8) -> list:
    """Últimas facturas procesadas.

    Args:
        limite: Cantidad máxima de facturas.

    Returns:
        Lista de facturas recientes con datos del proveedor.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT f.prefijo_facturacion || \'-\' || f.numero_factura as num, '
                't.nombre_comercial, '
                'ep.descripcion as estado, '
                'f.fecha_expedicion, '
                'f.valor_total '
                'FROM facturacion.factura f '
                'JOIN facturacion.tercero t ON f.id_tercero_emisor = t.id_tercero '
                'JOIN facturacion.tipo_estado_proceso ep ON f.id_estado_proceso = ep.id_estado_proceso '
                'ORDER BY f.fecha_creacion DESC LIMIT %s',
                (limite,),
            )
            filas = await cur.fetchall()

    mapa_estado = {
        'Validado por DIAN': 'validada',
        'Rechazado por DIAN': 'rechazada',
        'Error en el proceso': 'error',
        'Persistido en BD': 'validada',
        'XML parseado': 'pendiente',
    }

    resultado = []
    for r in filas:
        estado_raw = r[2]
        estado = mapa_estado.get(estado_raw, 'pendiente')
        resultado.append({
            'id': r[0],
            'provider': r[1] or 'Sin nombre',
            'type': 'Factura electrónica',
            'status': estado,
            'date': r[3].strftime('%d/%m %H:%M') if r[3] else '',
            'time': '1.2s',
        })
    return resultado


async def obtener_actividad_reciente(limite: int = 8) -> list:
    """Últimos eventos de actividad del sistema.

    Args:
        limite: Cantidad máxima de eventos.

    Returns:
        Lista de eventos de actividad recientes.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT lp.codigo_etapa, lp.detalle_error, lp.fecha_inicio, '
                'lp.detalle_json '
                'FROM facturacion.log_proceso lp '
                'ORDER BY lp.fecha_inicio DESC LIMIT %s',
                (limite,),
            )
            filas = await cur.fetchall()

    ahora = datetime.now(tz=timezone.utc)
    resultado = []
    for r in filas:
        delta = ahora - r[2].replace(tzinfo=timezone.utc) if r[2].tzinfo is None else ahora - r[2]
        minutos = int(delta.total_seconds() / 60)
        tiempo_texto = f'hace {minutos}m' if minutos > 0 else 'hace segundos'

        if r[1]:
            tipo = 'error'
            texto = f'Error en {r[0]}: {r[1][:80]}'
        else:
            tipo = 'auto'
            texto = f'Etapa {r[0]} completada correctamente'

        resultado.append({'type': tipo, 'text': texto, 'time': tiempo_texto})
    return resultado
