"""Router para la exportación de datos a Excel."""

import io
from datetime import date
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from core.python.services.exports_service import generar_reporte_excel
from core.python.services.facturas_service import listar_facturas, obtener_estadisticas

router = APIRouter(prefix="/api/exports", tags=["Exports"])

@router.get("/excel")
async def export_excel(
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None)
):
    """
    Endpoint para descargar el reporte de control en formato Excel.
    """
    wb, filename = await generar_reporte_excel(fecha_inicio, fecha_fin)
    
    # Guardar en un buffer de memoria
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"}
    )

@router.get("/query")
async def query_facturas(
    fecha_inicio: date = Query(None),
    fecha_fin: date = Query(None),
    page: int = Query(1, alias="page", ge=1),
    size: int = Query(10, alias="size", ge=1)
):
    """
    Endpoint para consultar la tabla de facturas con paginación y filtros de fecha.
    """
    # Reutilizamos la lógica de listar_facturas pero ajustada a los nuevos requerimientos
    # Para simplificar, implementamos la lógica directamente o extendemos el servicio existente.
    from core.python.db import get_pool
    import calendar
    
    pool = get_pool()
    if not fecha_inicio or not fecha_fin:
        hoy = date.today()
        fecha_inicio = hoy.replace(day=1)
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        fecha_fin = hoy.replace(day=ultimo_dia)

    offset = (page - 1) * size
    
    # Query para contar total de registros con filtros
    count_query = "SELECT COUNT(*) FROM facturacion.factura WHERE fecha_generacion::date BETWEEN %s AND %s"
    
    # Query para obtener datos paginados
    data_query = """
        SELECT f.id_factura, f.numero_factura, t.razon_social_emisor, f.valor_total, f.fecha_generacion
        FROM facturacion.factura f
        JOIN facturacion.tercero t ON f.id_tercero_emisor = t.id_tercero
        WHERE f.fecha_generacion::date BETWEEN %s AND %s
        ORDER BY f.fecha_creacion DESC
        LIMIT %s OFFSET %s
    """

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(count_query, [fecha_inicio, fecha_fin])
            total_records = (await cur.fetchone())[0]
            
            await cur.execute(data_query, [fecha_inicio, fecha_fin, size, offset])
            rows = await cur.fetchall()

    total_pages = (total_records + size - 1) // size
    
    return {
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
