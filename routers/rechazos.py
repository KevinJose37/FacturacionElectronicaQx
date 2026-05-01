"""Endpoints de la página de rechazos."""

import asyncio

from fastapi import APIRouter

from core import rechazos_service

router = APIRouter(prefix='/api/rechazos', tags=['rechazos'])


@router.get('')
async def obtener_rechazos() -> dict:
    """Obtiene rechazos con estadísticas y causas frecuentes."""
    stats, rechazos, causas = await asyncio.gather(
        rechazos_service.obtener_estadisticas(),
        rechazos_service.listar_rechazos(),
        rechazos_service.obtener_causas_frecuentes(),
    )

    respuesta = {'stats': stats, 'rejections': rechazos, 'causes': causas}
    return respuesta
