"""Endpoints del dashboard principal."""

import asyncio

from fastapi import APIRouter, Query

from core import alertas_dian_service, dashboard_service

router = APIRouter(prefix='/api/dashboard', tags=['dashboard'])


@router.get('')
async def obtener_dashboard(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    tipo_fecha: str = 'creacion',
    proveedores: list[str] = Query(None),
    formas_pago: list[str] = Query(None),
    medios_pago: list[str] = Query(None),
    impuestos: list[str] = Query(None),
    errores: list[str] = Query(None),
    eventos_dian: list[str] = Query(None),
    rangos_vencimiento: list[str] = Query(None),
) -> dict:
    """Obtiene todos los datos del dashboard en una sola llamada.

    Ejecuta todas las consultas en paralelo con asyncio.gather.
    
    Args:
        tipo_fecha: 'creacion' para fecha de procesamiento, 'expedicion' para fecha de emisión.
    """
    fecha_mas_antigua = await dashboard_service.obtener_fecha_mas_antigua()
    if not fecha_inicio:
        fecha_inicio = fecha_mas_antigua
    if not fecha_fin:
        from datetime import datetime
        fecha_fin = datetime.now().strftime('%Y-%m-%d')

    # Parse list filters safely
    def parse_list_filter(values: list[str] | None) -> list[str]:
        if not values:
            return []
        result = []
        for val in values:
            if ',' in val:
                result.extend([v.strip() for v in val.split(',') if v.strip()])
            else:
                result.append(val)
        return result

    filtros = {
        'proveedores': parse_list_filter(proveedores),
        'formas_pago': parse_list_filter(formas_pago),
        'medios_pago': parse_list_filter(medios_pago),
        'impuestos': parse_list_filter(impuestos),
        'errores': parse_list_filter(errores),
        'eventos_dian': parse_list_filter(eventos_dian),
        'rangos_vencimiento': parse_list_filter(rangos_vencimiento),
    }

    # Determine the column to filter by
    columna_fecha = 'fecha_expedicion' if tipo_fecha == 'expedicion' else 'fecha_creacion'

    filtros_sin_proveedores = {k: v for k, v in filtros.items() if k != 'proveedores'}
    filtros_sin_formas_pago = {k: v for k, v in filtros.items() if k != 'formas_pago'}
    filtros_sin_medios_pago = {k: v for k, v in filtros.items() if k != 'medios_pago'}
    filtros_sin_eventos_dian = {k: v for k, v in filtros.items() if k != 'eventos_dian'}
    filtros_sin_impuestos = {k: v for k, v in filtros.items() if k != 'impuestos'}
    filtros_sin_errores = {k: v for k, v in filtros.items() if k != 'errores'}

    (
        kpis, proveedores_data, tendencia, facturas,
        actividad, alertas, alertas_dian,
        valor_proveedor, forma_pago, medio_pago, eventos_dian, impuestos_data,
        eventos_min, funnel_ingesta, cuentas_por_pagar, top_errores
    ) = await asyncio.gather(
        dashboard_service.obtener_kpis(fecha_inicio, fecha_fin, columna_fecha, filtros),
        dashboard_service.obtener_facturas_por_proveedor(fecha_inicio, fecha_fin, columna_fecha=columna_fecha, filtros=filtros_sin_proveedores),
        dashboard_service.obtener_tendencia(fecha_inicio, fecha_fin, columna_fecha=columna_fecha, filtros=filtros),
        dashboard_service.obtener_ultimas_facturas(filtros=filtros),
        dashboard_service.obtener_actividad_reciente(),
        dashboard_service.obtener_alertas_activas(),
        alertas_dian_service.obtener_alertas_dian(),
        dashboard_service.obtener_valor_proveedor_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha, filtros=filtros_sin_proveedores),
        dashboard_service.obtener_forma_pago_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha, filtros=filtros_sin_formas_pago),
        dashboard_service.obtener_medio_pago_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha, filtros=filtros_sin_medios_pago),
        dashboard_service.obtener_eventos_dian_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha, filtros=filtros_sin_eventos_dian),
        dashboard_service.obtener_impuestos_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha, filtros=filtros_sin_impuestos),
        dashboard_service.obtener_eventos_por_minuto(),
        dashboard_service.obtener_funnel_ingesta(fecha_inicio, fecha_fin, filtros=filtros),
        dashboard_service.obtener_cuentas_por_pagar(fecha_inicio, fecha_fin, columna_fecha=columna_fecha, filtros=filtros),
        dashboard_service.obtener_top_errores_ingesta(fecha_inicio, fecha_fin, filtros=filtros_sin_errores),
    )

    respuesta = {
        'fecha_mas_antigua': fecha_mas_antigua,
        'kpis': kpis,
        'provider_data': proveedores_data,
        'trend_data': tendencia,
        'invoices': facturas,
        'activity': actividad,
        'alerts': alertas,
        'alertas_dian': alertas_dian,
        'valor_proveedor_data': valor_proveedor,
        'forma_pago_data': forma_pago,
        'medio_pago_data': medio_pago,
        'eventos_dian_data': eventos_dian,
        'impuestos_data': impuestos_data,
        'events_per_min': eventos_min,
        'funnel_ingesta_data': funnel_ingesta,
        'cuentas_por_pagar_data': cuentas_por_pagar,
        'top_errores_ingesta_data': top_errores,
    }
    return respuesta


@router.get('/kpis')
async def obtener_kpis() -> list:
    """Obtiene los KPIs del dashboard."""
    resultado = await dashboard_service.obtener_kpis()
    return resultado


@router.get('/flow')
async def obtener_flujo() -> list:
    """Obtiene las etapas del pipeline."""
    resultado = await dashboard_service.obtener_etapas_flujo()
    return resultado


@router.get('/alertas-dian')
async def obtener_alertas_dian(refresh: bool = Query(False)) -> dict:
    """Obtiene el reporte de alertas de eventos DIAN.

    Args:
        refresh: Si es True, fuerza el recálculo ignorando el caché.
    """
    from datetime import datetime, timezone
    
    fecha = datetime.now(tz=timezone.utc) if refresh else None
    resultado = await alertas_dian_service.obtener_alertas_dian(fecha_corte=fecha)
    return resultado


@router.post('/alertas/{id_alerta}/resolver')
async def resolver_alerta(id_alerta: int) -> dict:
    """Marca una alerta como resuelta."""
    exito = await dashboard_service.resolver_alerta(id_alerta)
    return {'success': exito}
