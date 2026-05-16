"""Servicio para la generación de reportes Excel."""

import logging
from datetime import date

from openpyxl import Workbook

from config import load_yaml_queries
from core.python.db import get_pool
from core.python.exports.excel_exporter import ExcelExporter
from metadata.fechas_metadata import MesesEspanol

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('excel/queries_excel.yml').get('exportacion', {})


async def generar_reporte_excel(
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
) -> tuple:
    """Obtiene los datos de la base de datos y genera el objeto Workbook de Excel.

    Args:
        fecha_inicio: Fecha inicial del rango de consulta.
        fecha_fin: Fecha final del rango de consulta.

    Returns:
        Tupla conteniendo el objeto Workbook y el nombre del archivo.
    """
    pool = get_pool()
    exporter = ExcelExporter()

    # Lógica de fechas por defecto (mes actual hasta hoy)
    fecha_ini = fecha_inicio
    fecha_f = fecha_fin

    if not fecha_ini or not fecha_f:
        hoy = date.today()
        fecha_ini = hoy.replace(day=1)
        fecha_f = hoy

    query = _QUERIES['generar_reporte']
    data = []

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, [fecha_ini, fecha_f])
                columnas = [desc[0] for desc in cur.description]
                filas = await cur.fetchall()
                data = [dict(zip(columnas, fila)) for fila in filas]
    except Exception as e:
        logger.error(f'Error en consulta de base de datos: {e}')
        # Reintentar una vez si la conexión falló
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, [fecha_ini, fecha_f])
                columnas = [desc[0] for desc in cur.description]
                filas = await cur.fetchall()
                data = [dict(zip(columnas, fila)) for fila in filas]

    if not fecha_inicio or not fecha_fin:
        month_label = MesesEspanol.mapa[fecha_ini.month]
        year_label = str(fecha_ini.year)
        filename = f'relacion_entrega_facturas_mes_{month_label.lower()}'
    else:
        month_label = f"{fecha_ini.strftime('%Y/%m/%d')} a {fecha_f.strftime('%Y/%m/%d')}"
        year_label = ''
        label_clean = month_label.replace('/', '_').replace(' a ', '_a_').replace(' ', '_')
        filename = f'relacion_entrega_facturas_{label_clean}'

    wb = exporter.generate_excel(data, month_label, year_label)
    resultado = (wb, filename)
    return resultado
