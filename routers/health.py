"""Endpoint de Healthcheck de la API."""

from fastapi import APIRouter
from core.python.services import health_service

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check() -> dict:
    """Verifica el estado del sistema y sus dependencias.

    Retorna 200 OK siempre, pero el JSON indicará si el servicio
    está 'ok', 'degraded' o 'error'.
    """
    return await health_service.get_health_status()
