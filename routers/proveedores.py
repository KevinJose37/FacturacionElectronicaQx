"""Endpoints de la página de proveedores."""

from fastapi import APIRouter

from core import proveedores_service

router = APIRouter(prefix='/api/proveedores', tags=['proveedores'])


@router.get('')
async def obtener_proveedores() -> dict:
    """Obtiene listado de proveedores con estadísticas."""
    stats = await proveedores_service.obtener_estadisticas()
    proveedores = await proveedores_service.listar_proveedores()

    respuesta = {'stats': stats, 'providers': proveedores}
    return respuesta
