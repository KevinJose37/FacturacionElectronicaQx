"""Endpoints de la página de facturas."""

from fastapi import APIRouter, Query

from core import facturas_service

router = APIRouter(prefix='/api/facturas', tags=['facturas'])


@router.get('')
async def obtener_facturas(
    estado: str | None = Query(None, description='Filtro por estado'),
    busqueda: str | None = Query(None, description='Búsqueda por texto'),
    pagina: int = Query(1, ge=1, description='Número de página'),
    por_pagina: int = Query(30, ge=1, le=100, description='Registros por página'),
) -> dict:
    """Obtiene listado de facturas con estadísticas."""
    stats = await facturas_service.obtener_estadisticas()
    facturas = await facturas_service.listar_facturas(estado, busqueda, pagina, por_pagina)

    respuesta = {'stats': stats, 'invoices': facturas}
    return respuesta
