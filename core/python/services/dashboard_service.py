"""Servicio de consultas para el dashboard principal."""

import logging
from datetime import datetime, timedelta, timezone

from config import load_yaml_config, load_yaml_queries
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

_QUERIES = load_yaml_queries('services/queries_services.yml').get('dashboard', {})


def _parsear_fechas(fecha_inicio: str | None, fecha_fin: str | None) -> tuple[datetime, datetime]:
    ahora = datetime.now(tz=timezone.utc)
    if fecha_inicio and fecha_fin:
        try:
            dt_inicio = datetime.fromisoformat(fecha_inicio).replace(tzinfo=timezone.utc)
            dt_fin = datetime.fromisoformat(fecha_fin).replace(tzinfo=timezone.utc, hour=23, minute=59, second=59)
            return dt_inicio, dt_fin
        except ValueError:
            pass
    
    # Default: últimos 7 días
    dt_inicio = ahora - timedelta(days=7)
    return dt_inicio, ahora


async def obtener_fecha_mas_antigua() -> str:
    """Obtiene la fecha de la factura más antigua en la base de datos.

    Returns:
        Fecha formateada como string (YYYY-MM-DD) o un valor por defecto si no hay facturas.
    """
    pool = get_pool()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT MIN(fecha_creacion) FROM facturacion.factura")
                row = await cur.fetchone()
                if row and row[0]:
                    return row[0].strftime('%Y-%m-%d')
    except Exception as e:
        logger.error(f"Error al obtener la fecha mas antigua: {e}")
    return '2020-01-01'


async def obtener_kpis(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Calcula los KPIs principales del dashboard.

    Returns:
        Lista de diccionarios con los KPIs calculados.
    """
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['kpis'], (dt_inicio, dt_fin, dt_inicio, dt_fin))
            row = await cur.fetchone()
            processed = row[0]
            validated = row[1]
            rejected = row[2]
            providers = row[3]
            total_value = float(row[4]) if row[4] else 0.0
            avg_time = float(row[5]) if row[5] else 0.0

    avg_time_formatted = f"{avg_time:.1f}s"
    total_value_formatted = f"$ {total_value:,.2f}"

    valores = {
        'processed': {'value': str(processed), 'delta': 0.0, 'spark': [max(0, processed - i) for i in range(12, 0, -1)]},
        'validated': {'value': str(validated), 'delta': 0.0, 'spark': [max(0, validated - i) for i in range(12, 0, -1)]},
        'rejected': {
            'value': str(rejected), 'delta': 0.0,
            'spark': [max(0, rejected - i) for i in range(12, 0, -1)],
        },
        'time': {
            'value': avg_time_formatted, 'delta': 0.0,
            'spark': [0.0] * 12,
        },
        'total_value': {
            'value': total_value_formatted, 'delta': 0.0,
            'spark': [max(0.0, total_value - i * 1000) for i in range(12, 0, -1)],
        },
        'providers': {
            'value': str(providers), 'delta': 0.0,
            'spark': [max(0, providers - i) for i in range(12, 0, -1)],
        },
    }

    kpis = []
    for item in KpiDefiniciones.items:
        datos = valores[item['key']]
        kpis.append({**item, **datos})

    return kpis


async def obtener_etapas_flujo(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Obtiene las etapas del pipeline con conteos.

    Returns:
        Lista de etapas del flujo con conteo y estado.
    """
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)

    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['etapas_flujo'], (dt_inicio, dt_fin))
            row = await cur.fetchone()
            total, validacion, procesamiento, erp, finalizado = row

    factor_warn = float(_dashboard_cfg.get('factor_pipeline_warn', 0.9))
    conteos = [total, validacion, procesamiento, finalizado]
    estados = ['ok', 'ok', 'warn' if procesamiento < validacion * factor_warn else 'ok', 'ok']

    etapas = []
    for i, item in enumerate(EtapasFlujo.items):
        etapas.append({**item, 'count': conteos[i], 'status': estados[i]})

    return etapas


async def obtener_facturas_por_proveedor(fecha_inicio: str | None = None, fecha_fin: str | None = None, limite: int = 6) -> list:
    """Top proveedores por cantidad de facturas globales.

    Args:
        limite: Cantidad máxima de proveedores a retornar.

    Returns:
        Lista de proveedores con conteo de facturas.
    """
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['facturas_por_proveedor'], (dt_inicio, dt_fin))
            filas = await cur.fetchall()

    resultado = [
        {'name': r[0] or DefaultTextos.sin_nombre, 'facturas': r[1]}
        for r in filas
    ]
    return resultado


async def obtener_tendencia(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Tendencia de procesamiento de facturas por día.

    Returns:
        Lista de datos de tendencia por día.
    """
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    d_ini = dt_inicio.date()
    d_fin = dt_fin.date()

    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['tendencia'], (d_ini, d_fin, d_ini, d_fin, d_ini, d_fin, d_ini, d_fin))
            filas = await cur.fetchall()

    resultado = [
        {
            'day': r[0].strftime('%Y-%m-%d') if r[0] else '',
            'recibo': r[1],
            'compra': r[2],
            'procesamiento': r[3]
        }
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
            'date': r[3].strftime('%d/%m/%Y %H:%M') if r[3] else '',
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


async def obtener_tipos_documento(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Conteo de documentos agrupados por tipo_documento.

    Usa la columna tipo_documento de la tabla factura para generar
    datos para el gráfico de torta (DocTypePie).

    Returns:
        Lista de diccionarios con nombre del tipo y conteo.
    """
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)

    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['tipos_documento'], (dt_inicio, dt_fin))
            filas = await cur.fetchall()

    resultado = [
        {'name': TiposDocumento.mapa.get(r[0], r[0]), 'value': r[1]}
        for r in filas
    ]
    return resultado


async def obtener_heatmap_errores(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Genera datos para el heatmap de errores por día de la semana y hora.

    Cuenta registros en proceso_ingesta donde id_error IS NOT NULL,
    agrupados por día de la semana (0=Lun..6=Dom) y hora del día.

    Returns:
        Lista de celdas con day (str), hour (int) y value (int).
    """
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)

    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['heatmap_errores'], (dt_inicio, dt_fin))
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
                _QUERIES['alertas_activas'],
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


async def obtener_valor_proveedor_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Obtiene los valores de facturación acumulados por proveedor."""
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['valor_proveedor_stats'], (dt_inicio, dt_fin))
            filas = await cur.fetchall()
    return [{'name': r[0] or DefaultTextos.sin_nombre, 'value': float(r[1]) if r[1] else 0.0} for r in filas]


async def obtener_forma_pago_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Obtiene conteo de facturas por forma de pago."""
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['forma_pago_stats'], (dt_inicio, dt_fin))
            filas = await cur.fetchall()
    return [{'name': r[0], 'value': r[1]} for r in filas]


async def obtener_medio_pago_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Obtiene conteo de facturas por medio de pago."""
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['medio_pago_stats'], (dt_inicio, dt_fin))
            filas = await cur.fetchall()
    return [{'name': r[0], 'value': r[1]} for r in filas]


async def obtener_eventos_dian_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Obtiene la cantidad de eventos DIAN por tipo de evento."""
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['eventos_dian_stats'], (dt_inicio, dt_fin))
            filas = await cur.fetchall()
    return [{'name': r[0], 'value': r[1]} for r in filas]


async def obtener_impuestos_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> list:
    """Obtiene la suma de valor por tipo de impuesto."""
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['impuestos_stats'], (dt_inicio, dt_fin))
            filas = await cur.fetchall()
    return [{'name': r[0], 'value': float(r[1]) if r[1] else 0.0} for r in filas]

