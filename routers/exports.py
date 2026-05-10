"""Router para la exportación de datos a Excel."""

import calendar
import io
from datetime import date
 
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
 
from config import get_queries_excel
from core.python.db import get_pool
from core.python.services.exports_service import generar_reporte_excel
from core.python.services.facturas_service import (
    listar_facturas,
    obtener_estadisticas,
)
 
router = APIRouter(prefix='/api/exports', tags=['Exports'])

_QUERIES = get_queries_excel().get('exportacion', {})

@router.get('/excel')
async def export_excel(
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None),
) -> StreamingResponse:
    """Endpoint para descargar el reporte de control en formato Excel.

    Args:
        fecha_inicio: Filtro opcional de fecha inicial.
        fecha_fin: Filtro opcional de fecha final.

    Returns:
        Respuesta de streaming con el contenido del archivo .xlsx.

    """
    wb, filename = await generar_reporte_excel(fecha_inicio, fecha_fin)

    # Guardar en un buffer de memoria
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    resultado = StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}.xlsx'},
    )

    return resultado


@router.get('/query')
async def query_facturas(
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None),
    page: int = Query(1, alias='page', ge=1),
    size: int = Query(10, alias='size', ge=1),
) -> dict:
    """Endpoint para consultar la tabla de facturas con paginación y filtros de fecha.

    Args:
        fecha_inicio: Filtro opcional de fecha inicial.
        fecha_fin: Filtro opcional de fecha final.
        page: Número de página (1-indexed).
        size: Cantidad de registros por página.

    Returns:
        Diccionario con listado de ítems y metadata de paginación.

    """
    pool = get_pool()
    if not fecha_inicio or not fecha_fin:
        hoy = date.today()
        fecha_inicio = hoy.replace(day=1)
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        fecha_fin = hoy.replace(day=ultimo_dia)

    offset = (page - 1) * size
    
    # Queries centralizadas
    count_query = _QUERIES['contar_facturas_rango']
    data_query = _QUERIES['listar_facturas_paginado']

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(count_query, [fecha_inicio, fecha_fin])
            total_records = (await cur.fetchone())[0]
            
            await cur.execute(data_query, [fecha_inicio, fecha_fin, size, offset])
            rows = await cur.fetchall()

    total_pages = (total_records + size - 1) // size
    
    resultado = {
        "items": [
            {
                "id": r[0],
                "number": r[1],
                "provider": r[2],
                "amount": float(r[3]),
                "date": r[4].isoformat()
            } for r in rows
        ],
        "pagination": {
            "page": page,
            "size": size,
            "total_records": total_records,
            "total_pages": total_pages
        }
    }

    return resultado
