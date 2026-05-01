"""Endpoints de la página de proveedores."""

import asyncio

from fastapi import APIRouter

from core import proveedores_service

router = APIRouter(prefix='/api/proveedores', tags=['proveedores'])


@router.get('')
async def obtener_proveedores() -> dict:
    """Obtiene listado de proveedores con estadísticas."""
    stats, proveedores = await asyncio.gather(
        proveedores_service.obtener_estadisticas(),
        proveedores_service.listar_proveedores(),
    )

    respuesta = {'stats': stats, 'providers': proveedores}
    return respuesta
