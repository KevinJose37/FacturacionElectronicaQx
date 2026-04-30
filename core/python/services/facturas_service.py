"""Servicio de consultas para la página de facturas."""

import logging

from config import get_queries_services
from core.python.db import get_pool
from metadata.common_metadata import DefaultTextos
from metadata.factura_metadata import EstadosFactura

logger = logging.getLogger(__name__)

_QUERIES = get_queries_services().get('facturas', {})
_FILTROS = get_queries_services().get('facturas_filtros', {})


async def listar_facturas(
    estado: str | None = None,
    busqueda: str | None = None,
    pagina: int = 1,
    por_pagina: int = 30,
) -> list:
    """Lista facturas con filtros opcionales y paginación.

    Args:
        estado: Filtro por estado (validada, pendiente, rechazada, error).
        busqueda: Texto libre para buscar en número o proveedor.
        pagina: Número de página (1-indexed).
        por_pagina: Cantidad de registros por página.

    Returns:
        Lista de facturas con datos del proveedor.
    """
    pool = get_pool()
    offset = (pagina - 1) * por_pagina

    condiciones = []
    params = []

    if estado and estado in EstadosFactura.mapa_ids:
        ids_estado = EstadosFactura.mapa_ids[estado]
        placeholders = ', '.join(['%s'] * len(ids_estado))
        condiciones.append(_FILTROS['estado'].format(placeholders=placeholders))
        params.extend(ids_estado)

    if busqueda:
        condiciones.append(_FILTROS['busqueda'])
        patron = f'%{busqueda}%'
        params.extend([patron, patron, patron])

    where = f'WHERE {" AND ".join(condiciones)}' if condiciones else ''
    params.extend([por_pagina, offset])

    query = _QUERIES['listar'].format(where=where)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        estado_txt = EstadosFactura.mapa_texto.get(r[5], 'pendiente')
        resultado.append({
            'id': r[0],
            'provider': r[1] or DefaultTextos.sin_nombre,
            'type': DefaultTextos.factura_electronica,
            'status': estado_txt,
            'amount': float(r[3]),
            'date': r[4].strftime(DefaultTextos.formato_fecha_corto) if r[4] else '',
            'time': '1.2s',
        })
    return resultado


async def obtener_estadisticas() -> dict:
    """Calcula estadísticas agregadas de facturas.

    Returns:
        Diccionario con total, validadas, pendientes, rechazadas, monto_total.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['estadisticas'])
            row = await cur.fetchone()

    estadisticas = {
        'total': row[0],
        'validadas': row[1],
        'pendientes': row[2],
        'rechazadas': row[3],
        'monto_total': float(row[4]),
    }
    return estadisticas
