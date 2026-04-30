"""Servicio de consultas para la página de validaciones."""

import logging

from core.db import get_pool

logger = logging.getLogger(__name__)


async def obtener_reglas_validacion() -> list:
    """Obtiene reglas de validación con conteo de resultados.

    Returns:
        Lista de reglas con passed, failed y severidad.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT lp.codigo_etapa, '
                'COUNT(*) FILTER (WHERE lp.detalle_error IS NULL) as passed, '
                'COUNT(*) FILTER (WHERE lp.detalle_error IS NOT NULL) as failed '
                'FROM facturacion.log_proceso lp '
                'GROUP BY lp.codigo_etapa '
                'ORDER BY (COUNT(*) FILTER (WHERE lp.detalle_error IS NOT NULL)) DESC'
            )
            filas = await cur.fetchall()

    mapa_reglas = {
        'RECEPCION': ('VAL-001', 'Correo recibido y clasificado', 'medium'),
        'VERIFICACION_ADJUNTO': ('VAL-002', 'Adjunto verificado (ZIP válido)', 'high'),
        'ESCANEO': ('VAL-003', 'Escaneo de seguridad (antimalware)', 'high'),
        'EXTRACCION_XML': ('VAL-004', 'XML extraído del archivo comprimido', 'medium'),
        'PARSEO': ('VAL-005', 'XML parseado (estructura válida)', 'high'),
        'VALIDACION_DIAN': ('VAL-006', 'Validación CUFE con DIAN', 'high'),
        'PERSISTENCIA': ('VAL-007', 'Persistido en base de datos', 'low'),
    }

    resultado = []
    for r in filas:
        etapa = r[0]
        info = mapa_reglas.get(etapa, (f'VAL-{etapa[:3]}', etapa, 'medium'))
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
        Diccionario con reglas activas, total passed/failed y tasa de éxito.
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
