"""Servicio de consultas para la página de facturas."""

import logging

from core.db import get_pool

logger = logging.getLogger(__name__)


async def listar_facturas(estado: str | None = None, busqueda: str | None = None, pagina: int = 1, por_pagina: int = 30) -> list:
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
    mapa_estado_id = {
        'validada': (7, 9),
        'pendiente': (5, 6),
        'rechazada': (8,),
        'error': (10,),
    }

    condiciones = []
    params = []

    if estado and estado in mapa_estado_id:
        placeholders = ', '.join(['%s'] * len(mapa_estado_id[estado]))
        condiciones.append(f'f.id_estado_proceso IN ({placeholders})')
        params.extend(mapa_estado_id[estado])

    if busqueda:
        condiciones.append(
            '(f.numero_factura ILIKE %s OR t.nombre_comercial ILIKE %s OR t.razon_social ILIKE %s)'
        )
        patron = f'%{busqueda}%'
        params.extend([patron, patron, patron])

    where = f'WHERE {" AND ".join(condiciones)}' if condiciones else ''

    query = (
        f'SELECT f.prefijo_facturacion || \'-\' || f.numero_factura as num, '
        f't.nombre_comercial, ep.descripcion, f.valor_total, '
        f'f.fecha_expedicion, f.id_estado_proceso '
        f'FROM facturacion.factura f '
        f'JOIN facturacion.tercero t ON f.id_tercero_emisor = t.id_tercero '
        f'JOIN facturacion.tipo_estado_proceso ep ON f.id_estado_proceso = ep.id_estado_proceso '
        f'{where} '
        f'ORDER BY f.fecha_creacion DESC LIMIT %s OFFSET %s'
    )
    params.extend([por_pagina, offset])

    mapa_estado_texto = {7: 'validada', 8: 'rechazada', 9: 'validada', 10: 'error', 5: 'pendiente', 6: 'pendiente'}

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    resultado = []
    for r in filas:
        estado_txt = mapa_estado_texto.get(r[5], 'pendiente')
        resultado.append({
            'id': r[0],
            'provider': r[1] or 'Sin nombre',
            'type': 'Factura electrónica',
            'status': estado_txt,
            'amount': float(r[3]),
            'date': r[4].strftime('%d/%m %H:%M') if r[4] else '',
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
            await cur.execute('SELECT COUNT(*) FROM facturacion.factura')
            total = (await cur.fetchone())[0]

            await cur.execute('SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso IN (7, 9)')
            validadas = (await cur.fetchone())[0]

            await cur.execute('SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso IN (5, 6)')
            pendientes = (await cur.fetchone())[0]

            await cur.execute('SELECT COUNT(*) FROM facturacion.factura WHERE id_estado_proceso IN (8, 10)')
            rechazadas = (await cur.fetchone())[0]

            await cur.execute('SELECT COALESCE(SUM(valor_total), 0) FROM facturacion.factura')
            monto = float((await cur.fetchone())[0])

    estadisticas = {
        'total': total,
        'validadas': validadas,
        'pendientes': pendientes,
        'rechazadas': rechazadas,
        'monto_total': monto,
    }
    return estadisticas
