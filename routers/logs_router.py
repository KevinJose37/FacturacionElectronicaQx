"""Endpoints de la página de logs."""

import asyncio

from fastapi import APIRouter, Query

from core import logs_service

router = APIRouter(prefix='/api/logs', tags=['logs'])


@router.get('')
async def obtener_logs(
    nivel: str | None = Query(None, description='Filtro por nivel'),
    busqueda: str | None = Query(None, description='Búsqueda por texto'),
) -> dict:
    """Obtiene logs del sistema con conteos."""
    stats, logs = await asyncio.gather(
        logs_service.obtener_conteos(),
        logs_service.listar_logs(nivel, busqueda),
    )

    respuesta = {'stats': stats, 'logs': logs}
    return respuesta


@router.get('/trail')
async def obtener_trail(
    q: str = Query(..., min_length=2, description='Nº factura, email o asunto'),
) -> dict:
    """Obtiene el trail completo de procesamiento para una factura o correo."""
    return await logs_service.obtener_trail(q)
