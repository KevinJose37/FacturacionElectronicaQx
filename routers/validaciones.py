"""Endpoints de la página de reglas de validación."""

from fastapi import APIRouter, Query

from core import validaciones_service

router = APIRouter(prefix='/api/validaciones', tags=['validaciones'])


@router.get('')
async def obtener_validaciones(
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict:
    """Obtiene reglas de validación con estadísticas.
    
    Args:
        fecha_inicio: Fecha inicio en formato YYYY-MM-DD (opcional).
        fecha_fin: Fecha fin en formato YYYY-MM-DD (opcional).
    """
    reglas = await validaciones_service.obtener_reglas_validacion(fecha_inicio, fecha_fin)
    stats = await validaciones_service.obtener_estadisticas(fecha_inicio, fecha_fin)
    tendencia = await validaciones_service.obtener_tendencia_7d()

    respuesta = {
        'stats': stats,
        'rules': reglas,
        'tendencia_7d': tendencia,
    }
    return respuesta


@router.get('/{etapa}/facturas')
async def obtener_facturas_fallidas(
    etapa: str,
    fecha_inicio: str | None = None,
    fecha_fin: str | None = None,
) -> dict:
    """Obtiene las facturas que fallaron una regla específica.
    
    Args:
        etapa: Código de referencia de la etapa (ej: 'PARSEO').
        fecha_inicio: Fecha inicio en formato YYYY-MM-DD (opcional).
        fecha_fin: Fecha fin en formato YYYY-MM-DD (opcional).
    """
    facturas = await validaciones_service.obtener_facturas_fallidas(etapa, fecha_inicio, fecha_fin)
    return {'facturas': facturas}
