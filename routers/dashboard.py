"""Endpoints del dashboard principal."""

from fastapi import APIRouter

from core import dashboard_service

router = APIRouter(prefix='/api/dashboard', tags=['dashboard'])


@router.get('')
async def obtener_dashboard() -> dict:
    """Obtiene todos los datos del dashboard en una sola llamada."""
    kpis = await dashboard_service.obtener_kpis()
    flow = await dashboard_service.obtener_etapas_flujo()
    proveedores = await dashboard_service.obtener_facturas_por_proveedor()
    tendencia = await dashboard_service.obtener_tendencia()
    facturas = await dashboard_service.obtener_ultimas_facturas()
    actividad = await dashboard_service.obtener_actividad_reciente()

    respuesta = {
        'kpis': kpis,
        'flow_stages': flow,
        'provider_data': proveedores,
        'doc_type_data': [],
        'trend_data': tendencia,
        'heatmap_data': [],
        'invoices': facturas,
        'activity': actividad,
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
