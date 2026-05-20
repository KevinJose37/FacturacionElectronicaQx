"""Endpoints del dashboard principal."""

import asyncio

from fastapi import APIRouter

from core import alertas_dian_service, dashboard_service

router = APIRouter(prefix='/api/dashboard', tags=['dashboard'])


@router.get('')
async def obtener_dashboard(fecha_inicio: str | None = None, fecha_fin: str | None = None) -> dict:
    """Obtiene todos los datos del dashboard en una sola llamada.

    Ejecuta todas las consultas en paralelo con asyncio.gather.
    """
    (
        kpis, proveedores, tendencia, facturas,
        actividad, alertas, alertas_dian,
        valor_proveedor, forma_pago, medio_pago, eventos_dian, impuestos,
        eventos_min
    ) = await asyncio.gather(
        dashboard_service.obtener_kpis(fecha_inicio, fecha_fin),
        dashboard_service.obtener_facturas_por_proveedor(fecha_inicio, fecha_fin),
        dashboard_service.obtener_tendencia(fecha_inicio, fecha_fin),
        dashboard_service.obtener_ultimas_facturas(),
        dashboard_service.obtener_actividad_reciente(),
        dashboard_service.obtener_alertas_activas(),
        alertas_dian_service.obtener_alertas_dian(),
        dashboard_service.obtener_valor_proveedor_stats(),
        dashboard_service.obtener_forma_pago_stats(),
        dashboard_service.obtener_medio_pago_stats(),
        dashboard_service.obtener_eventos_dian_stats(),
        dashboard_service.obtener_impuestos_stats(),
        dashboard_service.obtener_eventos_por_minuto(),
    )

    respuesta = {
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
