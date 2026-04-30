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

            # Una sola query con todos los conteos
            await cur.execute(
                'SELECT '
                'COUNT(*) FILTER (WHERE fecha_creacion >= %s) as hoy, '
                'COUNT(*) FILTER (WHERE fecha_creacion >= %s) as ayer, '
                'COUNT(*) FILTER (WHERE id_estado_proceso = 7) as validadas, '
                'COUNT(*) FILTER (WHERE id_estado_proceso IN (8, 10)) as rechazadas, '
                'COUNT(DISTINCT id_tercero_emisor) as proveedores '
                'FROM facturacion.factura',
                (inicio_hoy, inicio_ayer),
            )
            row = await cur.fetchone()
            procesadas_hoy = row[0]
            procesadas_ayer = row[1] or 1
            validadas = row[2]
            rechazadas = row[3]
            proveedores = row[4]

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
            await cur.execute(
                'SELECT '
                'COUNT(*) as total, '
                'COUNT(*) FILTER (WHERE id_estado_proceso >= 2) as validacion, '
                'COUNT(*) FILTER (WHERE id_estado_proceso >= 6) as procesamiento, '
                'COUNT(*) FILTER (WHERE id_estado_proceso IN (7, 9)) as erp, '
                'COUNT(*) FILTER (WHERE id_estado_proceso = 9) as finalizado '
                'FROM facturacion.factura'
            )
            row = await cur.fetchone()
            total, validacion, procesamiento, erp, finalizado = row

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


async def obtener_tipos_documento() -> list:
    """Conteo de documentos agrupados por tipo_documento.

    Usa la columna tipo_documento de la tabla factura para generar
    datos para el gráfico de torta (DocTypePie).

    Returns:
        Lista de diccionarios con nombre del tipo y conteo.
    """
    pool = get_pool()
    mapa_nombres = {
        'FE': 'Factura electrónica',
        'NC': 'Nota crédito',
        'ND': 'Nota débito',
        'DS': 'Documento soporte',
    }
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT tipo_documento, COUNT(*) '
                'FROM facturacion.factura '
                'GROUP BY tipo_documento '
                'ORDER BY COUNT(*) DESC'
            )
            filas = await cur.fetchall()

    resultado = [
        {'name': mapa_nombres.get(r[0], r[0]), 'value': r[1]}
        for r in filas
    ]
    return resultado


async def obtener_heatmap_errores(dias: int = 7) -> list:
    """Genera datos para el heatmap de errores por día de la semana y hora.

    Cuenta registros en log_proceso donde detalle_error IS NOT NULL,
    agrupados por día de la semana (0=Lun..6=Dom) y hora del día.

    Args:
        dias: Cantidad de días hacia atrás a considerar.

    Returns:
        Lista de celdas con day (str), hour (int) y value (int).
    """
    pool = get_pool()
    dias_nombre = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT EXTRACT(DOW FROM fecha_inicio)::int as dia, "
                "EXTRACT(HOUR FROM fecha_inicio)::int as hora, "
                "COUNT(*) as total "
                "FROM facturacion.log_proceso "
                "WHERE detalle_error IS NOT NULL "
                "AND fecha_inicio >= NOW() - make_interval(days => %s) "
                "GROUP BY dia, hora "
                "ORDER BY dia, hora",
                (dias,),
            )
            filas = await cur.fetchall()

    resultado = [
        {'day': dias_nombre[r[0]], 'hour': r[1], 'value': r[2]}
        for r in filas
    ]
    return resultado


async def obtener_indicadores_pipeline() -> dict:
    """Calcula indicadores del pie del pipeline de flujo.

    - SLA cumplido: % de procesos finalizados en < 5 minutos.
    - Facturas atascadas: procesos sin fecha_fin con > 1 hora.
    - Cola interna: eventos pendientes en evento_ingesta.

    Returns:
        Diccionario con sla, atascadas, cola.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Atascadas + SLA en una sola query sobre proceso_ingesta
            await cur.execute(
                "SELECT "
                "COUNT(*) FILTER (WHERE fecha_fin IS NULL "
                "AND fecha_inicio < NOW() - INTERVAL '1 hour') as atascadas, "
                "COUNT(*) FILTER (WHERE fecha_fin IS NOT NULL "
                "AND fecha_fin - fecha_inicio < INTERVAL '5 minutes') as sla_ok, "
                "COUNT(*) FILTER (WHERE fecha_fin IS NOT NULL) as sla_total "
                "FROM facturacion.proceso_ingesta"
            )
            row = await cur.fetchone()
            atascadas = row[0]
            sla = round((row[1] / max(row[2], 1)) * 100, 1)

            # Cola interna (tabla distinta)
            await cur.execute(
                "SELECT COUNT(*) FROM facturacion.evento_ingesta "
                "WHERE estado = 'PENDIENTE'"
            )
            cola = (await cur.fetchone())[0]

    indicadores = {
        'sla': f'{sla}%',
        'atascadas': str(atascadas),
        'cola': f'{cola} jobs',
    }
    return indicadores


async def obtener_eventos_por_minuto(ventana_minutos: int = 10) -> dict:
    """Calcula eventos procesados por minuto y porcentaje de capacidad.

    Cuenta registros en log_proceso dentro de una ventana de tiempo
    y calcula la tasa por minuto.

    Args:
        ventana_minutos: Ventana de tiempo en minutos para el cálculo.

    Returns:
        Diccionario con events_per_min (float) y capacity_pct (int).
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM facturacion.log_proceso "
                "WHERE fecha_inicio >= NOW() - make_interval(mins => %s)",
                (ventana_minutos,),
            )
            eventos = (await cur.fetchone())[0]

    epm = round(eventos / max(ventana_minutos, 1), 1)
    capacidad_max = 200  # threshold configurable
    pct = min(round((epm / capacidad_max) * 100), 100)

    return {'events_per_min': epm, 'capacity_pct': pct}
