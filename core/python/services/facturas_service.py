"""Servicio de consultas para la página de facturas."""

import logging

from config import load_yaml_queries
from core.python.db import get_pool
from metadata.common_metadata import DefaultTextos
from metadata.factura_metadata import EstadosFactura

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('services/queries_services.yml').get('facturas', {})
_FILTROS = load_yaml_queries('services/queries_services.yml').get('facturas_filtros', {})


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
        if busqueda == 'sin_evento_030':
            condiciones.append("pf.codigo_forma_pago != '1' AND (fc.eventos_dian_notif IS NULL OR fc.eventos_dian_notif NOT LIKE '%%030%%')")
        elif busqueda == 'sin_evento_032':
            condiciones.append("pf.codigo_forma_pago != '1' AND (fc.eventos_dian_notif IS NULL OR fc.eventos_dian_notif NOT LIKE '%%032%%')")
        elif busqueda == 'sin_evento_033':
            condiciones.append("pf.codigo_forma_pago != '1' AND (fc.eventos_dian_notif IS NULL OR fc.eventos_dian_notif NOT LIKE '%%033%%')")
        elif busqueda == 'con_evento_rechazo':
            condiciones.append("pf.codigo_forma_pago != '1' AND fc.eventos_dian_notif LIKE '%%031%%'")
        else:
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
            'db_id': r[6],
            'provider': r[1] or DefaultTextos.sin_nombre,
            'type': DefaultTextos.factura_electronica,
            'status': estado_txt,
            'amount': float(r[3]),
            'date': r[4].strftime(DefaultTextos.formato_fecha_corto) if r[4] else '',
            'time': '1.2s',
            's3_key': r[6] or '',
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


async def obtener_pdf_s3_key(id_factura: int) -> str | None:
    """Busca la llave S3 del PDF asociado a una factura.

    Args:
        id_factura: ID de la factura.

    Returns:
        Ruta del archivo PDF en S3 o None si no se encuentra.
    """
    pool = get_pool()
    query = """
        SELECT ac.uri_almacenamiento
        FROM facturacion.adjuntos_correo ac
        WHERE ac.id_tipo_archivo = 3 -- 3 = PDF
          AND ac.correo_id = (
              SELECT correo_id 
              FROM facturacion.adjuntos_correo 
              WHERE adjunto_id = (
                  SELECT adjunto_id 
                  FROM facturacion.factura 
                  WHERE id_factura = %s
              )
          )
        LIMIT 1
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, [id_factura])
            row = await cur.fetchone()
            return row[0] if row else None


async def obtener_pdf_factura(id_factura: int) -> tuple[bytes, str] | None:
    """Descarga el contenido PDF de una factura desde S3.

    Args:
        id_factura: ID de la factura.

    Returns:
        Tupla con (contenido_bytes, nombre_archivo) o None si no existe.
    """
    s3_key = await obtener_pdf_s3_key(id_factura)
    if not s3_key:
        return None

    # Reutilizar el servicio de control para descargar desde S3
    from core.python.services import control_service
    contenido = await control_service.obtener_xml_factura(s3_key)

    if not contenido:
        return None

    filename = s3_key.split('/')[-1]
    return contenido, filename

