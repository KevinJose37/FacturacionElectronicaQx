"""Endpoints del dashboard principal."""

import asyncio

from fastapi import APIRouter

from core import alertas_dian_service, dashboard_service

router = APIRouter(prefix='/api/dashboard', tags=['dashboard'])


@router.get('')
async def obtener_dashboard(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
    tipo_fecha: str = 'creacion',
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

    # Determine the column to filter by
    columna_fecha = 'fecha_expedicion' if tipo_fecha == 'expedicion' else 'fecha_creacion'

    (
        kpis, proveedores, tendencia, facturas,
        actividad, alertas, alertas_dian,
        valor_proveedor, forma_pago, medio_pago, eventos_dian, impuestos,
        eventos_min, funnel_ingesta, cuentas_por_pagar, top_errores
    ) = await asyncio.gather(
        dashboard_service.obtener_kpis(fecha_inicio, fecha_fin, columna_fecha),
        dashboard_service.obtener_facturas_por_proveedor(fecha_inicio, fecha_fin, columna_fecha=columna_fecha),
        dashboard_service.obtener_tendencia(fecha_inicio, fecha_fin),
        dashboard_service.obtener_ultimas_facturas(),
        dashboard_service.obtener_actividad_reciente(),
        dashboard_service.obtener_alertas_activas(),
        alertas_dian_service.obtener_alertas_dian(),
        dashboard_service.obtener_valor_proveedor_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha),
        dashboard_service.obtener_forma_pago_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha),
        dashboard_service.obtener_medio_pago_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha),
        dashboard_service.obtener_eventos_dian_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha),
        dashboard_service.obtener_impuestos_stats(fecha_inicio, fecha_fin, columna_fecha=columna_fecha),
        dashboard_service.obtener_eventos_por_minuto(),
        dashboard_service.obtener_funnel_ingesta(fecha_inicio, fecha_fin),
        dashboard_service.obtener_cuentas_por_pagar(fecha_inicio, fecha_fin, columna_fecha=columna_fecha),
        dashboard_service.obtener_top_errores_ingesta(fecha_inicio, fecha_fin),
    )

    respuesta = {
        'fecha_mas_antigua': fecha_mas_antigua,
        'kpis': kpis,
        'provider_data': proveedores,
        'trend_data': tendencia,
        'invoices': facturas,
        'activity': actividad,
        'alerts': alertas,
        'alertas_dian': alertas_dian,
        'valor_proveedor_data': valor_proveedor,
        'forma_pago_data': forma_pago,
        'medio_pago_data': medio_pago,
        'eventos_dian_data': eventos_dian,
        'impuestos_data': impuestos,
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
async def obtener_alertas_dian() -> dict:
    """Obtiene el reporte de alertas de eventos DIAN.

    Retorna facturas sin eventos 030, 032, 033 y
    facturas con evento de rechazo 031, agrupadas por año y mes.
    Solo para facturas con forma_pago diferente a Contado.
    """
    resultado = await alertas_dian_service.obtener_alertas_dian()
    return resultado
