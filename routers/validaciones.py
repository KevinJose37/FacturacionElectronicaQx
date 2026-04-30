"""Endpoints de la página de validaciones."""

from fastapi import APIRouter

from core import validaciones_service

router = APIRouter(prefix='/api/validaciones', tags=['validaciones'])


@router.get('')
async def obtener_validaciones() -> dict:
    """Obtiene reglas de validación con estadísticas."""
    stats = await validaciones_service.obtener_estadisticas()
    reglas = await validaciones_service.obtener_reglas_validacion()

    respuesta = {'stats': stats, 'rules': reglas}
    return respuesta
