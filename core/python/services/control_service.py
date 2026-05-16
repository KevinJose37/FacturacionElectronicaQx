"""Servicio de consultas y actualización para la página de control de facturas."""

import calendar
import logging
from datetime import date

from config import get_queries_control
from core.python.db import get_pool

logger = logging.getLogger(__name__)

_QUERIES = get_queries_control().get('control', {})


async def listar_control(
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    """Lista registros de control de facturas con paginación y filtro de fechas.

    Args:
        fecha_inicio: Fecha inicial del rango de consulta.
        fecha_fin: Fecha final del rango de consulta.
        page: Número de página (1-indexed).
        size: Cantidad de registros por página.

    Returns:
        Diccionario con items paginados y metadata de paginación.
    """
    pool = get_pool()

    if not fecha_inicio or not fecha_fin:
        hoy = date.today()
        fecha_inicio = hoy.replace(day=1)
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        fecha_fin = hoy.replace(day=ultimo_dia)

    offset = (page - 1) * size

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['contar'], [fecha_inicio, fecha_fin])
            total_records = (await cur.fetchone())[0]

            await cur.execute(
                _QUERIES['listar'],
                [fecha_inicio, fecha_fin, size, offset],
            )
            filas = await cur.fetchall()

    total_pages = (total_records + size - 1) // size

    items = []
    for r in filas:
        items.append({
            'id_control': r[0],
            'fecha_admision_proveedor': r[1].isoformat() if r[1] else '',
            'medio_recepcion': r[2] or '',
            'fecha_entrega_contabilidad': r[3].isoformat() if r[3] else '',
            'nombre_recibe_contabilidad': r[4] or '',
            'nit_proveedor': r[5] or '',
            'nombre_proveedor': r[6] or '',
            'numero_factura': r[7] or '',
            'forma_pago': r[8] or '',
            'acuso_recibido': bool(r[9]),
            'recibido_bien_servicio': bool(r[10]),
            'aceptacion_empresa': bool(r[11]),
            'observaciones_entrega': r[12] or '',
            'eventos_dian_notif': r[13] or '',
        })

    resultado = {
        'items': items,
        'pagination': {
            'page': page,
            'size': size,
            'total_records': total_records,
            'total_pages': total_pages,
        },
    }
    return resultado


async def actualizar_control(id_control: int, datos: dict) -> bool:
    """Actualiza los campos editables de un registro de control.

    Args:
        id_control: Identificador del registro de control.
        datos: Diccionario con los campos a actualizar.

    Returns:
        True si se actualizó al menos un registro, False en caso contrario.
    """
    pool = get_pool()

    params = [
        datos.get('fecha_entrega_contabilidad'),
        datos.get('nombre_recibe_contabilidad'),
        datos.get('forma_pago'),
        datos.get('acuso_recibido', False),
        datos.get('recibido_bien_servicio', False),
        datos.get('aceptacion_empresa', False),
        datos.get('observaciones_entrega'),
        datos.get('eventos_dian_notif'),
        id_control,
    ]

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['actualizar'], params)
            filas_afectadas = cur.rowcount
        await conn.commit()

    resultado = filas_afectadas > 0
    return resultado
