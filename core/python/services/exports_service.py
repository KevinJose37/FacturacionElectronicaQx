"""Servicio para la generación de reportes Excel."""

import calendar
import logging
from datetime import date, datetime
 
from core.python.db import get_pool
from core.python.exports.excel_exporter import ExcelExporter
from metadata.fechas_metadata import MesesEspanol
 
logger = logging.getLogger(__name__)
 
async def generar_reporte_excel(fecha_inicio: date = None, fecha_fin: date = None):
    """
    Obtiene los datos de la base de datos y genera el objeto Workbook de Excel.
    """
    pool = get_pool()
    exporter = ExcelExporter()
    
    # Flag para saber si se usaron filtros
    usa_filtros = True if fecha_inicio and fecha_fin else False
    
    # Lógica de fechas por defecto (mes actual hasta hoy)
    if not fecha_inicio or not fecha_fin:
        hoy = date.today()
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy  # Hasta la fecha de la petición
    
    # Consulta SQL directa a facturacion.factura con todos los campos
    query = """
        SELECT id_factura, cufe, denominacion, 
               prefijo_facturacion, numero_factura, id_tercero_emisor, razon_social_emisor, 
               id_tercero_adquiriente, razon_social_adquiriente, id_autorizacion, 
               fecha_generacion, fecha_expedicion, fecha_vencimiento, codigo_moneda, 
               valor_total, hash_firma_digital, contenido_qr, adjunto_id, 
               id_estado_proceso, fecha_creacion, fecha_actualizacion
        FROM facturacion.factura
        WHERE fecha_generacion::date BETWEEN %s AND %s
        ORDER BY fecha_creacion DESC
    """
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, [fecha_inicio, fecha_fin])
                columnas = [desc[0] for desc in cur.description]
                filas = await cur.fetchall()
                data = [dict(zip(columnas, fila)) for fila in filas]
    except Exception as e:
        logger.error(f"Error en consulta de base de datos: {e}")
        # Reintentar una vez si la conexión falló
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, [fecha_inicio, fecha_fin])
                columnas = [desc[0] for desc in cur.description]
                filas = await cur.fetchall()
                data = [dict(zip(columnas, fila)) for fila in filas]
 
    if not usa_filtros:
        month_label = MesesEspanol.mapa[fecha_inicio.month]
        year_label = str(fecha_inicio.year)
        filename = f"Relación entrega facturas_MES {month_label}"
    else:
        month_label = f"{fecha_inicio.strftime('%Y/%m/%d')} a {fecha_fin.strftime('%Y/%m/%d')}"
        year_label = ""
        filename = f"Relación entrega facturas {month_label}"
        
    wb = exporter.generate_excel(data, month_label, year_label)
    
    return wb, filename
