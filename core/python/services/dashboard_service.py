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
            fi = fecha_inicio.split('T')[0]
            ff = fecha_fin.split('T')[0]
            dt_inicio = datetime.strptime(fi, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            dt_fin = datetime.strptime(ff, "%Y-%m-%d").replace(tzinfo=timezone.utc, hour=23, minute=59, second=59)
            return dt_inicio, dt_fin
        except Exception as e:
            logger.error(f"Error parseando fechas: {e}")
            pass
    
    # Default: últimos 7 días
    dt_inicio = ahora - timedelta(days=7)
    return dt_inicio, ahora


_COLUMNAS_FECHA_VALIDAS = {'fecha_creacion', 'fecha_expedicion'}

def _col_fecha(columna: str) -> str:
    """Validates and returns a safe column name for date filtering."""
    if columna not in _COLUMNAS_FECHA_VALIDAS:
        return 'fecha_creacion'
    return columna


def construir_subconsulta_filtros(filtros: dict | None) -> tuple[str, list]:
    if not filtros:
        return "", []
    
    subquery_parts = []
    subquery_params = []
    
    proveedores = filtros.get('proveedores')
    if proveedores:
        subquery_parts.append(f"f_sub.razon_social_emisor IN ({','.join(['%s']*len(proveedores))})")
        subquery_params.extend(proveedores)

    formas_pago = filtros.get('formas_pago')
    if formas_pago:
        subquery_parts.append(f"COALESCE(tf_sub.descripcion, pf_sub.codigo_forma_pago, 'No definido') IN ({','.join(['%s']*len(formas_pago))})")
        subquery_params.extend(formas_pago)

    medios_pago = filtros.get('medios_pago')
    if medios_pago:
        subquery_parts.append(f"COALESCE(tmp_sub.descripcion, pf_sub.codigo_medio_pago, 'No definido') IN ({','.join(['%s']*len(medios_pago))})")
        subquery_params.extend(medios_pago)

    impuestos = filtros.get('impuestos')
    if impuestos:
        subquery_parts.append(f"COALESCE(ti_sub.nombre, ti_sub.descripcion, im_sub.codigo_impuesto, 'Otros') IN ({','.join(['%s']*len(impuestos))})")
        subquery_params.extend(impuestos)

    errores = filtros.get('errores')
    if errores:
        subquery_parts.append(f"te_sub.descripcion IN ({','.join(['%s']*len(errores))})")
        subquery_params.extend(errores)

    eventos_dian = filtros.get('eventos_dian')
    if eventos_dian:
        subquery_parts.append(f"COALESCE(ted_sub.nombre_evento, edf_sub.codigo_evento, 'No definido') IN ({','.join(['%s']*len(eventos_dian))})")
        subquery_params.extend(eventos_dian)

    rangos_vencimiento = filtros.get('rangos_vencimiento')
    if rangos_vencimiento:
        rango_clause = """(CASE 
            WHEN f_sub.fecha_vencimiento <= CURRENT_DATE THEN 'Vencidas'
            WHEN f_sub.fecha_vencimiento <= CURRENT_DATE + INTERVAL '7 days' THEN 'Próximos 7 días'
            WHEN f_sub.fecha_vencimiento <= CURRENT_DATE + INTERVAL '15 days' THEN '8 a 15 días'
            WHEN f_sub.fecha_vencimiento <= CURRENT_DATE + INTERVAL '30 days' THEN '16 a 30 días'
            ELSE 'Más de 30 días'
        END)"""
        subquery_parts.append(f"{rango_clause} IN ({','.join(['%s']*len(rangos_vencimiento))})")
        subquery_params.extend(rangos_vencimiento)

    if not subquery_parts:
        return "", []

    subquery = f"""
        SELECT DISTINCT f_sub.id_factura 
        FROM facturacion.factura f_sub
        LEFT JOIN facturacion.pago_factura pf_sub ON f_sub.id_factura = pf_sub.id_factura
        LEFT JOIN facturacion.tipo_forma_pago tf_sub ON pf_sub.codigo_forma_pago = tf_sub.codigo_forma_pago
        LEFT JOIN facturacion.tipo_medio_pago tmp_sub ON pf_sub.codigo_medio_pago = tmp_sub.codigo_medio_pago
        LEFT JOIN facturacion.evento_dian_factura edf_sub ON f_sub.id_factura = edf_sub.id_factura
        LEFT JOIN facturacion.tipo_evento_dian ted_sub ON edf_sub.codigo_evento = ted_sub.codigo_evento
        LEFT JOIN facturacion.impuesto_factura im_sub ON f_sub.id_factura = im_sub.id_factura
        LEFT JOIN facturacion.tipo_impuesto ti_sub ON im_sub.codigo_impuesto = ti_sub.codigo_impuesto
        LEFT JOIN facturacion.proceso_ingesta pi_sub ON f_sub.adjunto_id = pi_sub.adjunto_id
        LEFT JOIN facturacion.tipo_error te_sub ON pi_sub.id_error = te_sub.id_tipo_error
        WHERE {" AND ".join(subquery_parts)}
    """
    return subquery, subquery_params


def aplicar_subconsulta(query_base: str, col_id_factura: str, subquery: str) -> str:
    if not subquery:
        return query_base
    if "GROUP BY" in query_base:
        parts = query_base.split("GROUP BY", 1)
        return f"{parts[0]} AND {col_id_factura} IN ({subquery}) GROUP BY {parts[1]}"
    else:
        return f"{query_base} AND {col_id_factura} IN ({subquery})"


async def obtener_fecha_mas_antigua() -> str:
    """Obtiene la fecha de la factura más antigua en la base de datos.

    Returns:
        Fecha formateada como string (YYYY-MM-DD) o un valor por defecto si no hay facturas.
    """
    pool = get_pool()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT MIN(fecha_expedicion) FROM facturacion.factura")
                row = await cur.fetchone()
                if row and row[0]:
                    return row[0].strftime('%Y-%m-%d')
    except Exception as e:
        logger.error(f"Error al obtener la fecha mas antigua: {e}")
    return '2020-01-01'


async def obtener_kpis(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion', filtros: dict = None) -> list:
    """Calcula los KPIs principales del dashboard.

    Returns:
        Lista de diccionarios con los KPIs calculados.
    """
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    # Replace fecha_creacion with the selected column in the KPIs query
    query = _QUERIES['kpis'].replace('fecha_creacion', col)
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    query = aplicar_subconsulta(query, 'id_factura', subquery)
    params = (dt_inicio, dt_fin, dt_inicio, dt_fin)
    if subquery:
        params += tuple(subquery_params)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            row = await cur.fetchone()
            processed = row[0]
            validated = row[1]
            rejected = row[2]
            pending_human = row[3]
            providers = row[4]
            total_value = float(row[5]) if row[5] else 0.0
            avg_time = float(row[6]) if row[6] else 0.0

    avg_time_formatted = f"{avg_time:.1f}s"
    total_value_formatted = f"$ {total_value:,.2f}"

    valores = {
        'processed': {'value': str(processed), 'delta': 0.0, 'spark': [max(0, processed - i) for i in range(12, 0, -1)]},
        'validated': {'value': str(validated), 'delta': 0.0, 'spark': [max(0, validated - i) for i in range(12, 0, -1)]},
        'rejected': {
            'value': str(rejected), 'delta': 0.0,
            'spark': [max(0, rejected - i) for i in range(12, 0, -1)],
        },
        'pending_human': {
            'value': str(pending_human), 'delta': 0.0,
            'spark': [max(0, pending_human - i) for i in range(12, 0, -1)],
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


async def obtener_etapas_flujo(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion', filtros: dict = None) -> list:
    """Obtiene las etapas del pipeline con conteos.

    Returns:
        Lista de etapas del flujo con conteo y estado.
    """
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)

    pool = get_pool()
    query = _QUERIES['etapas_flujo'].replace('fecha_creacion', col)
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    query = aplicar_subconsulta(query, 'id_factura', subquery)
    params = (dt_inicio, dt_fin)
    if subquery:
        params += tuple(subquery_params)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            row = await cur.fetchone()
            total, validacion, procesamiento, erp, finalizado = row

    factor_warn = float(_dashboard_cfg.get('factor_pipeline_warn', 0.9))
    conteos = [total, validacion, procesamiento, finalizado]
    estados = ['ok', 'ok', 'warn' if procesamiento < validacion * factor_warn else 'ok', 'ok']

    etapas = []
    for i, item in enumerate(EtapasFlujo.items):
        etapas.append({**item, 'count': conteos[i], 'status': estados[i]})

    return etapas


async def obtener_facturas_por_proveedor(fecha_inicio: str | None = None, fecha_fin: str | None = None, limite: int = 6, columna_fecha: str = 'fecha_creacion', filtros: dict = None) -> list:
    """Top proveedores por cantidad de facturas globales."""
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    query = _QUERIES['facturas_por_proveedor'].replace('fecha_creacion', col)
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    query = aplicar_subconsulta(query, 'f.id_factura', subquery)
    params = (dt_inicio, dt_fin)
    if subquery:
        params += tuple(subquery_params)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    resultado = [
        {'name': r[0] or DefaultTextos.sin_nombre, 'facturas': r[1]}
        for r in filas
    ]
    return resultado


async def obtener_tendencia(fecha_inicio: str | None = None, fecha_fin: str | None = None, filtros: dict = None) -> list:
    """Tendencia de procesamiento de facturas por día.

    Returns:
        Lista de datos de tendencia por día.
    """
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    d_ini = dt_inicio.date()
    d_fin = dt_fin.date()

    pool = get_pool()
    query = _QUERIES['tendencia']
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    
    if subquery:
        query = query.replace(
            "WHERE fc.fecha_admision_proveedor >= %s AND fc.fecha_admision_proveedor <= %s",
            f"WHERE fc.fecha_admision_proveedor >= %s AND fc.fecha_admision_proveedor <= %s AND fc.id_factura IN ({subquery})"
        )
        query = query.replace(
            "WHERE f.fecha_expedicion::date >= %s AND f.fecha_expedicion::date <= %s",
            f"WHERE f.fecha_expedicion::date >= %s AND f.fecha_expedicion::date <= %s AND f.id_factura IN ({subquery})"
        )
        query = query.replace(
            "WHERE f.fecha_creacion::date >= %s AND f.fecha_creacion::date <= %s",
            f"WHERE f.fecha_creacion::date >= %s AND f.fecha_creacion::date <= %s AND f.id_factura IN ({subquery})"
        )
        
        params = (
            d_ini, d_fin,
            d_ini, d_fin,
        )
        params += tuple(subquery_params)
        
        params += (d_ini, d_fin,)
        params += tuple(subquery_params)
        
        params += (d_ini, d_fin,)
        params += tuple(subquery_params)
    else:
        params = (d_ini, d_fin, d_ini, d_fin, d_ini, d_fin, d_ini, d_fin)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
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


async def obtener_ultimas_facturas(limite: int = 8, filtros: dict = None) -> list:
    """Últimas facturas procesadas.

    Args:
        limite: Cantidad máxima de facturas.

    Returns:
        Lista de facturas recientes con datos del proveedor.
    """
    pool = get_pool()
    query = _QUERIES['ultimas_facturas']
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    
    if subquery:
        query = query.replace("ORDER BY f.fecha_creacion", f"WHERE f.id_factura IN ({subquery}) ORDER BY f.fecha_creacion")
        params = tuple(subquery_params) + (limite,)
    else:
        params = (limite,)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        estado = EstadosFactura.mapa_descripcion.get(r[2], 'pendiente')
        resultado.append({
            'id': r[0],
            'provider': r[1] or DefaultTextos.sin_nombre,
            'type': DefaultTextos.factura_electronica,
            'status': estado,
            'date': r[3].strftime('%Y-%m-%d') if r[3] else '',
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


async def obtener_tipos_documento(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion') -> list:
    """Conteo de documentos agrupados por tipo_documento."""
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)

    pool = get_pool()
    query = _QUERIES['tipos_documento'].replace('fecha_creacion', col)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (dt_inicio, dt_fin))
            filas = await cur.fetchall()

    resultado = [
        {'name': TiposDocumento.mapa.get(r[0], r[0]), 'value': r[1]}
        for r in filas
    ]
    return resultado


async def obtener_heatmap_errores(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion') -> list:
    """Genera datos para el heatmap de errores por día de la semana y hora."""
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)

    pool = get_pool()
    query = _QUERIES['heatmap_errores'].replace('fecha_creacion', col)
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (dt_inicio, dt_fin))
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

async def obtener_alertas_activas(limite: int = 50) -> list:
    """Obtiene las alertas activas (no resueltas) más recientes resumidas por factura."""
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                _QUERIES['alertas_activas'],
                (limite,)
            )
            filas = await cur.fetchall()

    vistas_facturas = {}
    alertas_finales = []
    import re
    
    # Patrón para limpiar errores técnicos de base de datos
    patron_tecnico = r'Último error: current transaction is aborted, commands ignored until end of transaction block'

    for r in filas:
        # r[0]=id, r[1]=tipo, r[2]=prioridad, r[3]=titulo, r[4]=mensaje, r[5]=fecha, r[6]=remitente, r[7]=asunto
        # r[8]=fecha_correo, r[9]=correo_id, r[10]=id_factura, r[11]=num_factura, r[12]=fecha_factura, r[13]=proveedor
        # r[14]=xml_s3_key, r[15]=pdf_s3_key, r[16]=xml_nombre, r[17]=pdf_nombre
        id_factura = r[10]
        mensaje_original = r[4]
        remitente = r[6]
        asunto = r[7]
        fecha_correo = r[8].strftime('%d/%m/%Y %H:%M') if r[8] else None
        correo_id = r[9]
        num_factura = r[11]
        fecha_factura = r[12].strftime('%d/%m/%Y') if r[12] else None
        proveedor = r[13]
        xml_s3_key = r[14]
        pdf_s3_key = r[15]
        xml_nombre = r[16]
        pdf_nombre = r[17]
        
        # 1. Limpieza de errores técnicos
        mensaje_limpio = re.sub(patron_tecnico, '', mensaje_original).strip()
        
        # 2. Gestión de metadatos (Filtrar "Sin Asunto")
        asunto_limpio = asunto if asunto and asunto.lower() != 'sin asunto' else None
        
        # Limpieza de remitente
        email_limpio = None
        if remitente:
            match_email = re.search(r'[\w\.-]+@[\w\.-]+', remitente)
            email_limpio = match_email.group(0) if match_email else remitente

        item = {
            'id': r[0],
            'type': r[1],
            'priority': r[2],
            'title': r[3],
            'message': mensaje_limpio,
            'date': r[5].isoformat() if r[5] else '',
            'email': email_limpio,
            'asunto': asunto_limpio,
            'fecha_correo': fecha_correo,
            'correo_id': correo_id,
            'xml_s3_key': xml_s3_key,
            'pdf_s3_key': pdf_s3_key,
            'xml_nombre': xml_nombre,
            'pdf_nombre': pdf_nombre,
            'factura': {
                'id': id_factura,
                'numero': num_factura,
                'fecha': fecha_factura,
                'proveedor': proveedor
            } if num_factura else None
        }

        # Determinación de la clave de agrupación (por correo_id, o número y emisor, o id_factura)
        clave_factura = None
        if correo_id:
            clave_factura = f"correo_{correo_id}"
        elif num_factura and proveedor:
            clave_factura = (str(num_factura).strip().upper(), str(proveedor).strip().upper())
        elif id_factura:
            clave_factura = id_factura

        if clave_factura:
            if clave_factura in vistas_facturas:
                # Ya existe una alerta para esta factura/correo, agrupamos
                grupo = vistas_facturas[clave_factura]
                
                # Concatenar el mensaje si es diferente
                if mensaje_limpio not in grupo['_mensajes_lista']:
                    grupo['_mensajes_lista'].append(mensaje_limpio)
                
                # Mantener la prioridad más crítica
                prioridades = ['CRITICA', 'ALTA', 'MEDIA', 'BAJA']
                prio_nueva = item['priority']
                if prio_nueva in prioridades:
                    idx_nueva = prioridades.index(prio_nueva)
                    idx_actual = prioridades.index(grupo['priority'])
                    if idx_nueva < idx_actual:
                        grupo['priority'] = prio_nueva
                
                # Si la nueva alerta tiene datos de factura y el grupo no, los adoptamos
                if item['factura'] and not grupo['factura']:
                    grupo['factura'] = item['factura']
                elif item['factura'] and grupo['factura']:
                    if item['factura']['id'] and not grupo['factura']['id']:
                        grupo['factura']['id'] = item['factura']['id']
            else:
                # Primera alerta de esta factura
                item['_mensajes_lista'] = [mensaje_limpio]
                vistas_facturas[clave_factura] = item
                alertas_finales.append(item)
        else:
            # Alertas del sistema
            alertas_finales.append(item)

    # Dar formato final de lista a los mensajes agrupados
    for f_key, grupo in vistas_facturas.items():
        if len(grupo['_mensajes_lista']) > 1:
            bullet_points = "\n".join(f"• {m}" for m in grupo['_mensajes_lista'])
            grupo['message'] = f"Se detectaron múltiples observaciones en esta factura:\n{bullet_points}"
            grupo['title'] = "Factura con múltiples observaciones"
        grupo.pop('_mensajes_lista', None)

    return alertas_finales



async def obtener_valor_proveedor_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion', filtros: dict = None) -> list:
    """Obtiene los valores de facturación acumulados por proveedor."""
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    query = _QUERIES['valor_proveedor_stats'].replace('fecha_creacion', col)
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    query = aplicar_subconsulta(query, 'f.id_factura', subquery)
    params = (dt_inicio, dt_fin)
    if subquery:
        params += tuple(subquery_params)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()
    return [{'name': r[0] or DefaultTextos.sin_nombre, 'value': float(r[1]) if r[1] else 0.0} for r in filas]


async def obtener_forma_pago_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion', filtros: dict = None) -> list:
    """Obtiene conteo de facturas por forma de pago."""
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    query = _QUERIES['forma_pago_stats'].replace('fecha_creacion', col)
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    query = aplicar_subconsulta(query, 'f.id_factura', subquery)
    params = (dt_inicio, dt_fin)
    if subquery:
        params += tuple(subquery_params)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()
    return [{'name': r[0], 'value': r[1]} for r in filas]


async def obtener_medio_pago_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion', filtros: dict = None) -> list:
    """Obtiene conteo de facturas por medio de pago."""
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    query = _QUERIES['medio_pago_stats'].replace('fecha_creacion', col)
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    query = aplicar_subconsulta(query, 'f.id_factura', subquery)
    params = (dt_inicio, dt_fin)
    if subquery:
        params += tuple(subquery_params)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()
    return [{'name': r[0], 'value': r[1]} for r in filas]


async def obtener_eventos_dian_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion', filtros: dict = None) -> list:
    """Obtiene la cantidad de eventos DIAN por tipo de evento."""
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    query = _QUERIES['eventos_dian_stats'].replace('fecha_creacion', col)
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    query = aplicar_subconsulta(query, 'f.id_factura', subquery)
    params = (dt_inicio, dt_fin)
    if subquery:
        params += tuple(subquery_params)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()
    return [{'name': r[0], 'value': r[1]} for r in filas]


async def obtener_impuestos_stats(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion', filtros: dict = None) -> list:
    """Obtiene la suma de valor por tipo de impuesto."""
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    query = _QUERIES['impuestos_stats'].replace('fecha_creacion', col)
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    query = aplicar_subconsulta(query, 'f.id_factura', subquery)
    params = (dt_inicio, dt_fin)
    if subquery:
        params += tuple(subquery_params)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()
    return [{'name': r[0], 'value': float(r[1]) if r[1] else 0.0} for r in filas]


async def obtener_funnel_ingesta(fecha_inicio: str | None = None, fecha_fin: str | None = None, filtros: dict = None) -> dict:
    """Obtiene los conteos del embudo de ingesta contable."""
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    
    try:
        if subquery:
            query = f"""
                SELECT
                (SELECT COUNT(*) FROM facturacion.correo_entrante WHERE fecha_deteccion >= %s AND fecha_deteccion <= %s
                 AND correo_id IN (SELECT DISTINCT ac.correo_id FROM facturacion.adjuntos_correo ac JOIN facturacion.factura f_sub ON ac.adjunto_id = f_sub.adjunto_id WHERE f_sub.id_factura IN ({subquery}))) as correos,
                
                (SELECT COUNT(*) FROM facturacion.adjuntos_correo ac JOIN facturacion.correo_entrante c ON ac.correo_id = c.correo_id JOIN facturacion.factura f_sub ON ac.adjunto_id = f_sub.adjunto_id WHERE c.fecha_deteccion >= %s AND c.fecha_deteccion <= %s
                 AND f_sub.id_factura IN ({subquery})) as adjuntos,
                
                (SELECT COUNT(DISTINCT adjunto_id) FROM facturacion.evento_ingesta WHERE fecha_creacion >= %s AND fecha_creacion <= %s
                 AND adjunto_id IN (SELECT f_sub.adjunto_id FROM facturacion.factura f_sub WHERE f_sub.id_factura IN ({subquery}))) as procesados,
                
                (SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso = 3 AND fecha_creacion >= %s AND fecha_creacion <= %s
                 AND id_factura IN ({subquery})) as validados
            """
            params = []
            # correos
            params.extend([dt_inicio, dt_fin])
            params.extend(subquery_params)
            # adjuntos
            params.extend([dt_inicio, dt_fin])
            params.extend(subquery_params)
            # procesados
            params.extend([dt_inicio, dt_fin])
            params.extend(subquery_params)
            # validados
            params.extend([dt_inicio, dt_fin])
            params.extend(subquery_params)
        else:
            query = _QUERIES['funnel_ingesta']
            params = [dt_inicio, dt_fin, dt_inicio, dt_fin, dt_inicio, dt_fin, dt_inicio, dt_fin]

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
                if row:
                    return {
                        'correos': row[0] or 0,
                        'adjuntos': row[1] or 0,
                        'procesados': row[2] or 0,
                        'validados': row[3] or 0
                    }
    except Exception as e:
        logger.error(f"Error al obtener funnel ingesta: {e}")
    return {'correos': 0, 'adjuntos': 0, 'procesados': 0, 'validados': 0}


async def obtener_cuentas_por_pagar(fecha_inicio: str | None = None, fecha_fin: str | None = None, columna_fecha: str = 'fecha_creacion', filtros: dict = None) -> list:
    """Obtiene la proyección de cuentas por pagar agrupadas por rango de vencimiento."""
    col = _col_fecha(columna_fecha)
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    query = _QUERIES['cuentas_por_pagar'].replace('fecha_creacion', col)
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    query = aplicar_subconsulta(query, 'f.id_factura', subquery)
    params = (dt_inicio, dt_fin)
    if subquery:
        params += tuple(subquery_params)

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                filas = await cur.fetchall()
                return [
                    {
                        'rango': r[0],
                        'total': float(r[1]) if r[1] else 0.0,
                        'cantidad': r[2] or 0
                    }
                    for r in filas
                ]
    except Exception as e:
        logger.error(f"Error al obtener cuentas por pagar: {e}")
    return []


async def obtener_top_errores_ingesta(fecha_inicio: str | None = None, fecha_fin: str | None = None, filtros: dict = None) -> list:
    """Obtiene los 5 errores más frecuentes durante la ingesta."""
    dt_inicio, dt_fin = _parsear_fechas(fecha_inicio, fecha_fin)
    pool = get_pool()
    query = _QUERIES['top_errores_ingesta']
    
    subquery, subquery_params = construir_subconsulta_filtros(filtros)
    if subquery:
        query = query.replace("WHERE", f"JOIN facturacion.factura f ON pi.adjunto_id = f.adjunto_id WHERE f.id_factura IN ({subquery}) AND")
        params = tuple(subquery_params) + (dt_inicio, dt_fin)
    else:
        params = (dt_inicio, dt_fin)

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                filas = await cur.fetchall()
                return [
                    {
                        'error': r[0] or "Otro",
                        'total': r[1] or 0
                    }
                    for r in filas
                ]
    except Exception as e:
        logger.error(f"Error al obtener top errores: {e}")
    return []


async def resolver_alerta(id_alerta: int) -> bool:
    """Marca una alerta (y sus agrupadas de la misma factura) como resueltas en la base de datos."""
    pool = get_pool()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Obtener la factura_id, adjunto_id y metadatos de la factura asociada
                await cur.execute(
                    """
                    SELECT a.factura_id, a.adjunto_id, f.numero_factura, f.id_tercero_emisor, ac.correo_id
                    FROM facturacion.alerta a
                    LEFT JOIN facturacion.factura f ON f.id_factura = a.factura_id
                    LEFT JOIN facturacion.adjuntos_correo ac ON ac.adjunto_id = a.adjunto_id
                    WHERE a.id_alerta = %s
                    """,
                    (id_alerta,)
                )
                row = await cur.fetchone()
                if row:
                    factura_id, adjunto_id, numero_factura, id_tercero_emisor, correo_id = row
                    
                    # Si la alerta tiene un correo_id asociado, resolvemos todas las alertas de ese correo
                    if correo_id:
                        await cur.execute(
                            """
                            UPDATE facturacion.alerta 
                            SET resuelta = TRUE 
                            WHERE id_alerta IN (
                                SELECT a2.id_alerta 
                                FROM facturacion.alerta a2
                                JOIN facturacion.adjuntos_correo ac2 ON ac2.adjunto_id = a2.adjunto_id
                                WHERE ac2.correo_id = %s
                            ) OR adjunto_id = %s OR factura_id = %s
                            """,
                            (correo_id, adjunto_id, factura_id)
                        )
                        # También resolvemos por número de factura y emisor si aplica
                        if numero_factura and id_tercero_emisor:
                            await cur.execute(
                                """
                                UPDATE facturacion.alerta 
                                SET resuelta = TRUE 
                                WHERE id_alerta IN (
                                    SELECT a2.id_alerta 
                                    FROM facturacion.alerta a2
                                    JOIN facturacion.factura f2 ON f2.id_factura = a2.factura_id
                                    WHERE f2.numero_factura = %s AND f2.id_tercero_emisor = %s
                                )
                                """,
                                (numero_factura, id_tercero_emisor)
                            )
                        return True
                    
                    # Si no tiene correo_id, pero tiene factura vinculada con número y emisor, resolvemos por esos campos
                    if numero_factura and id_tercero_emisor:
                        await cur.execute(
                            """
                            UPDATE facturacion.alerta 
                            SET resuelta = TRUE 
                            WHERE id_alerta IN (
                                SELECT a2.id_alerta 
                                FROM facturacion.alerta a2
                                JOIN facturacion.factura f2 ON f2.id_factura = a2.factura_id
                                WHERE f2.numero_factura = %s AND f2.id_tercero_emisor = %s
                            ) OR adjunto_id = %s OR factura_id = %s
                            """,
                            (numero_factura, id_tercero_emisor, adjunto_id, factura_id)
                        )
                        return True
                    
                    if factura_id:
                        # Resolver todas las del mismo factura_id
                        await cur.execute(
                            "UPDATE facturacion.alerta SET resuelta = TRUE WHERE factura_id = %s OR adjunto_id = %s",
                            (factura_id, adjunto_id)
                        )
                        return True
                    elif adjunto_id:
                        # Resolver todas las del mismo adjunto_id
                        await cur.execute(
                            "UPDATE facturacion.alerta SET resuelta = TRUE WHERE adjunto_id = %s",
                            (adjunto_id,)
                        )
                        return True
                
                # Fallback standard single alert resolve
                await cur.execute(
                    "UPDATE facturacion.alerta SET resuelta = TRUE WHERE id_alerta = %s",
                    (id_alerta,)
                )
                return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Error al resolver alerta {id_alerta}: {e}")
        return False

