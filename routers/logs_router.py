"""Endpoints de la página de logs."""

from fastapi import APIRouter, Query

from core import logs_service

router = APIRouter(prefix='/api/logs', tags=['logs'])


@router.get('')
async def obtener_logs(
    nivel: str | None = Query(None, description='Filtro por nivel'),
    busqueda: str | None = Query(None, description='Búsqueda por texto'),
) -> dict:
    """Obtiene logs del sistema con conteos."""
    stats = await logs_service.obtener_conteos()
    logs = await logs_service.listar_logs(nivel, busqueda)

    respuesta = {'stats': stats, 'logs': logs}
    return respuesta
