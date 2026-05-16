"""Servicio de consultas para la página de validaciones."""

import logging

from config import load_yaml_queries
from core.python.db import get_pool
from metadata.validacion_metadata import ReglasValidacion

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('services/queries_services.yml').get('validaciones', {})


async def obtener_reglas_validacion() -> list:
    """Obtiene reglas de validación con conteo de resultados.

    Returns:
        Lista de reglas con código, descripción, passed, failed y severidad.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['reglas'])
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        etapa = r[0]
        info = ReglasValidacion.mapa.get(etapa, (f'VAL-{etapa[:3]}', etapa, 'medium'))
        resultado.append({
            'code': info[0],
            'rule': info[1],
            'passed': r[1],
            'failed': r[2],
            'severity': info[2],
        })
    return resultado


async def obtener_estadisticas() -> dict:
    """Calcula estadísticas agregadas de validaciones.

    Returns:
        Diccionario con reglas_activas, total_passed, total_failed, tasa_exito.
    """
    reglas = await obtener_reglas_validacion()
    total_passed = sum(r['passed'] for r in reglas)
    total_failed = sum(r['failed'] for r in reglas)
    total = total_passed + total_failed
    tasa = round((total_passed / max(total, 1)) * 100, 2)

    estadisticas = {
        'reglas_activas': len(reglas),
        'total_passed': total_passed,
        'total_failed': total_failed,
        'tasa_exito': tasa,
    }
    return estadisticas
