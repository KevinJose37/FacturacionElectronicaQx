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
            inicio_hoy = ahora - timedelta(days=30)
            inicio_ayer = inicio_hoy - timedelta(days=30)

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
        'validated': {'value': str(validadas), 'delta': 0.0, 'spark': [max(0, validadas - i) for i in range(12, 0, -1)]},
        'rejected': {
            'value': str(rechazadas), 'delta': 0.0,
            'spark': [max(0, rechazadas - i) for i in range(12, 0, -1)],
        },
        'time': {
            'value': '0.0s', 'delta': 0.0,
            'spark': [0.0] * 12,
        },
        'auto': {
            'value': f'{pct_auto}%', 'delta': 0.0,
            'spark': [max(0, pct_auto - i * 0.5) for i in range(12, 0, -1)],
        },
        'providers': {
            'value': str(proveedores), 'delta': 0.0,
            'spark': [max(0, proveedores - i) for i in range(12, 0, -1)],
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
            'amount': float(r[4]) if r[4] else 0,
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
        # r[0]=etapa, r[1]=detalle_error, r[2]=fecha_inicio, r[3]=num_factura
        fecha_log = r[2].replace(tzinfo=timezone.utc) if r[2] and r[2].tzinfo is None else r[2]
        num_factura = f'{r[3]}: ' if len(r) > 3 and r[3] else ''

        if fecha_log:
            delta = ahora - fecha_log
            minutos = int(delta.total_seconds() / 60)
            tiempo_texto = FormatoTiempo.desde_minutos(minutos)
        else:
            tiempo_texto = FormatoTiempo.nunca

        if r[1]:
            tipo = MensajesLog.nivel_error
            detalle_truncado = r[1][:80]
            texto = MensajesLog.error_prefijo.format(etapa=r[0], detalle=detalle_truncado)
        else:
            tipo = MensajesLog.tipo_auto
            texto = MensajesLog.completado.format(etapa=r[0])

        texto_final = f'{num_factura}{texto}'
        resultado.append({'type': tipo, 'text': texto_final, 'time': tiempo_texto})
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

    Cuenta registros en proceso_ingesta donde id_error IS NOT NULL,
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

    Cuenta registros en proceso_ingesta dentro de una ventana de tiempo
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
    """Obtiene las alertas activas (no resueltas) más recientes.

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
                SELECT a.id_alerta, a.codigo_tipo_alerta, a.codigo_prioridad, 
                       a.titulo, a.mensaje, a.fecha_creacion, c.remitente, c.asunto
                FROM facturacion.alerta a
                LEFT JOIN facturacion.correo_entrante c ON a.correo_id = c.correo_id
                WHERE a.resuelta = FALSE
                ORDER BY
                  CASE a.codigo_prioridad
                    WHEN 'CRITICA' THEN 1
                    WHEN 'ALTA' THEN 2
                    WHEN 'MEDIA' THEN 3
                    WHEN 'BAJA' THEN 4
                    ELSE 5
                  END,
                  a.fecha_creacion DESC
                LIMIT %s
                """,
                (limite,)
            )
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        # r[0]=id, r[1]=tipo, r[2]=prioridad, r[3]=titulo, r[4]=mensaje, r[5]=fecha, r[6]=remitente, r[7]=asunto
        mensaje_original = r[4]
        remitente = r[6]
        asunto = r[7] or 'Sin Asunto'
        
        # Si existe el remitente (email real), intentamos limpiar el mensaje de alertas de correo
        mensaje_final = mensaje_original
        if remitente and ('fue identificado como facturación' in mensaje_original or 'Adjunto incompleto en correo' in mensaje_original):
            import re
            
            # Limpiar el nombre del remitente si viene con formato MIME o caracteres especiales
            # Ejemplo: "=?iso-8859-1?Q?Iv=E1n... <email>" -> "email"
            match_email = re.search(r'[\w\.-]+@[\w\.-]+', remitente)
            email_limpio = match_email.group(0) if match_email else remitente
            
            # Construir el nuevo mensaje con Asunto y Remitente limpio
            if 'fue identificado como facturación' in mensaje_original:
                patron = r'El correo [^ ]+ fue identificado como facturación'
                reemplazo = f'El correo con Asunto: "{asunto}" de {email_limpio} fue identificado como facturación'
                mensaje_final = re.sub(patron, reemplazo, mensaje_original)
            
            if 'Adjunto incompleto en correo' in mensaje_original:
                patron = r'Adjunto incompleto en correo [^:]+:'
                reemplazo = f'Adjunto incompleto en correo con Asunto: "{asunto}" de {email_limpio}:'
                mensaje_final = re.sub(patron, reemplazo, mensaje_final)

        resultado.append({
            'id': r[0],
            'type': r[1],
            'priority': r[2],
            'title': r[3],
            'message': mensaje_final,
            'date': r[5].isoformat() if r[5] else '',
        })
    return resultado
