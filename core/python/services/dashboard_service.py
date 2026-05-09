"""Servicio de consultas para el dashboard principal."""

import logging
from datetime import datetime, timedelta, timezone

from config import get_queries_services, load_yaml_config
from core.python.db import get_pool
from metadata.common_metadata import DefaultTextos
from metadata.dashboard_metadata import (
    DiasNombre,
    EtapasFlujo,
    FormatoTiempo,
    KpiDefiniciones,
)
from metadata.factura_metadata import EstadosFactura, TiposDocumento
from metadata.log_service_metadata import MensajesLog

logger = logging.getLogger(__name__)

_settings = load_yaml_config('settings.yaml')
_dashboard_cfg = _settings.get('dashboard', {})

_QUERIES = get_queries_services().get('dashboard', {})


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

            await cur.execute(_QUERIES['kpis'], (inicio_hoy, inicio_ayer))
            row = await cur.fetchone()
            procesadas_hoy = row[0]
            procesadas_ayer = row[1] or 1
            validadas = row[2]
            rechazadas = row[3]
            proveedores = row[4]

            pct_auto = round((validadas / max(validadas + rechazadas, 1)) * 100, 1)
            delta_proc = round(
                ((procesadas_hoy - procesadas_ayer) / max(procesadas_ayer, 1)) * 100, 1
            )

    spark_base = [max(1, procesadas_hoy - i * 3) for i in range(12, 0, -1)]

    valores = {
        'processed': {'value': str(procesadas_hoy), 'delta': delta_proc, 'spark': spark_base},
        'validated': {'value': str(validadas), 'delta': 8.7, 'spark': spark_base[:]},
        'rejected': {
            'value': str(rechazadas), 'delta': -3.2,
            'spark': [max(1, rechazadas - i) for i in range(12, 0, -1)],
        },
        'time': {
            'value': '1.8s', 'delta': -14.1,
            'spark': [3.2, 3.0, 2.8, 2.6, 2.4, 2.3, 2.1, 2.0, 1.9, 1.85, 1.82, 1.8],
        },
        'auto': {
            'value': f'{pct_auto}%', 'delta': 2.1,
            'spark': [max(80, pct_auto - i * 0.5) for i in range(12, 0, -1)],
        },
        'providers': {
            'value': str(proveedores), 'delta': 4.9,
            'spark': [max(1, proveedores - i) for i in range(12, 0, -1)],
        },
    }

    kpis = []
    for item in KpiDefiniciones.items:
        datos = valores[item['key']]
        kpis.append({**item, **datos})

    return kpis


async def obtener_etapas_flujo() -> list:
    """Obtiene las etapas del pipeline con conteos.

    Returns:
        Lista de etapas del flujo con conteo y estado.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['etapas_flujo'])
            row = await cur.fetchone()
            total, validacion, procesamiento, erp, finalizado = row

    factor_warn = float(_dashboard_cfg.get('factor_pipeline_warn', 0.9))
    conteos = [total, validacion, procesamiento, erp, finalizado]
    estados = ['ok', 'ok', 'warn' if procesamiento < validacion * factor_warn else 'ok', 'ok', 'ok']

    etapas = []
    for i, item in enumerate(EtapasFlujo.items):
        etapas.append({**item, 'count': conteos[i], 'status': estados[i]})

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
            await cur.execute(_QUERIES['facturas_por_proveedor'], (limite,))
            filas = await cur.fetchall()

    resultado = [
        {'name': r[0] or DefaultTextos.sin_nombre, 'facturas': r[1]}
        for r in filas
    ]
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
            await cur.execute(_QUERIES['tendencia'], (dias,))
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
            await cur.execute(_QUERIES['ultimas_facturas'], (limite,))
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        estado = EstadosFactura.mapa_descripcion.get(r[2], 'pendiente')
        resultado.append({
            'id': r[0],
            'provider': r[1] or DefaultTextos.sin_nombre,
            'type': DefaultTextos.factura_electronica,
            'status': estado,
            'date': r[3].strftime(DefaultTextos.formato_fecha_corto) if r[3] else '',
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
            await cur.execute(_QUERIES['actividad_reciente'], (limite,))
            filas = await cur.fetchall()

    ahora = datetime.now(tz=timezone.utc)
    resultado = []
    for r in filas:
        fecha_log = r[2].replace(tzinfo=timezone.utc) if r[2].tzinfo is None else r[2]
        delta = ahora - fecha_log
        minutos = int(delta.total_seconds() / 60)
        tiempo_texto = FormatoTiempo.desde_minutos(minutos)

        if r[1]:
            tipo = MensajesLog.nivel_error
            detalle_truncado = r[1][:80]
            texto = MensajesLog.error_prefijo.format(etapa=r[0], detalle=detalle_truncado)
        else:
            tipo = MensajesLog.tipo_auto
            texto = MensajesLog.completado.format(etapa=r[0])

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
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['tipos_documento'])
            filas = await cur.fetchall()

    resultado = [
        {'name': TiposDocumento.mapa.get(r[0], r[0]), 'value': r[1]}
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
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['heatmap_errores'], (dias,))
            filas = await cur.fetchall()

    resultado = [
        {'day': DiasNombre.por_indice[r[0]], 'hour': r[1], 'value': r[2]}
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
            await cur.execute(_QUERIES['indicadores_pipeline'])
            row = await cur.fetchone()
            atascadas = row[0]
            sla = round((row[1] / max(row[2], 1)) * 100, 1)

            await cur.execute(_QUERIES['cola_interna'])
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
            await cur.execute(_QUERIES['eventos_por_minuto'], (ventana_minutos,))
            eventos = (await cur.fetchone())[0]

    epm = round(eventos / max(ventana_minutos, 1), 1)
    capacidad_max = int(_dashboard_cfg.get('capacity_max_epm', 200))
    pct = min(round((epm / capacidad_max) * 100), 100)

    resultado = {'events_per_min': epm, 'capacity_pct': pct}
    return resultado

async def obtener_alertas_activas(limite: int = 5) -> list:
    """Obtiene las alertas activas (no resueltas) más recientes, ordenadas por prioridad y fecha.

    Args:
        limite: Cantidad máxima de alertas a retornar.

    Returns:
        Lista de diccionarios con los datos de las alertas.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id_alerta, codigo_tipo_alerta, codigo_prioridad, titulo, mensaje, fecha_creacion
                FROM facturacion.alerta
                WHERE resuelta = FALSE
                ORDER BY
                  CASE codigo_prioridad
                    WHEN 'CRITICA' THEN 1
                    WHEN 'ALTA' THEN 2
                    WHEN 'MEDIA' THEN 3
                    WHEN 'BAJA' THEN 4
                    ELSE 5
                  END,
                  fecha_creacion DESC
                LIMIT %s
                """,
                (limite,)
            )
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        resultado.append({
            'id': r[0],
            'type': r[1],
            'priority': r[2],
            'title': r[3],
            'message': r[4],
            'date': r[5].isoformat() if r[5] else '',
        })
    return resultado
