"""Endpoints del dashboard principal."""

import asyncio

from fastapi import APIRouter

from core import alertas_dian_service, dashboard_service

router = APIRouter(prefix='/api/dashboard', tags=['dashboard'])


@router.get('')
async def obtener_dashboard() -> dict:
    """Obtiene todos los datos del dashboard en una sola llamada.

    Ejecuta todas las consultas en paralelo con asyncio.gather.
    """
    (
        kpis, flow, proveedores, tendencia, facturas,
        actividad, tipos_doc, heatmap, indicadores, eventos_min, alertas,
        alertas_dian
    ) = await asyncio.gather(
        dashboard_service.obtener_kpis(),
        dashboard_service.obtener_etapas_flujo(),
        dashboard_service.obtener_facturas_por_proveedor(),
        dashboard_service.obtener_tendencia(),
        dashboard_service.obtener_ultimas_facturas(),
        dashboard_service.obtener_actividad_reciente(),
        dashboard_service.obtener_tipos_documento(),
        dashboard_service.obtener_heatmap_errores(),
        dashboard_service.obtener_indicadores_pipeline(),
        dashboard_service.obtener_eventos_por_minuto(),
        dashboard_service.obtener_alertas_activas(),
        alertas_dian_service.obtener_alertas_dian(),
    )

    respuesta = {
        'kpis': kpis,
        'flow_stages': flow,
        'flow_indicators': indicadores,
        'provider_data': proveedores,
        'doc_type_data': tipos_doc,
        'trend_data': tendencia,
        'heatmap_data': heatmap,
        'invoices': facturas,
        'activity': actividad,
        'events_per_min': eventos_min,
        'alerts': alertas,
        'alertas_dian': alertas_dian,
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
