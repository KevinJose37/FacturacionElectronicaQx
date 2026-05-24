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

    if estado == 'manual':
        condiciones.append("f.verificacion_grafica_estado = 'PENDIENTE'")
    elif estado and estado in EstadosFactura.mapa_ids:
        ids_estado = EstadosFactura.mapa_ids[estado]
        placeholders = ', '.join(['%s'] * len(ids_estado))
        condiciones.append(_FILTROS['estado'].format(placeholders=placeholders))
        params.extend(ids_estado)

    if busqueda:
        if busqueda == 'verificacion_manual':
            condiciones.append("f.verificacion_grafica_estado = 'PENDIENTE'")
        elif busqueda == 'sin_evento_030':
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
        estado_txt = EstadosFactura.mapa_texto.get(r[6], 'pendiente')
        resultado.append({
            'id': r[0],
            'db_id': r[4],
            'provider': r[1] or DefaultTextos.sin_nombre,
            'type': DefaultTextos.factura_electronica,
            'status': estado_txt,
            'amount': float(r[3]) if r[3] is not None else 0.0,
            'date': r[5].strftime(DefaultTextos.formato_fecha_corto) if r[5] else '',
            'time': '1.2s',
            'motivo_rechazo': r[10] or '',
            'verificacion_grafica_estado': r[11] or '',
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
    
    # 1. Obtener adjunto_id y correo_id para depuración
    query_ids = """
        SELECT f.adjunto_id, ac.correo_id, ac.nombre_archivo
        FROM facturacion.factura f
        LEFT JOIN facturacion.adjuntos_correo ac ON f.adjunto_id = ac.adjunto_id
        WHERE f.id_factura = %s
    """
    
    adjunto_id = None
    correo_id = None
    xml_name = None
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query_ids, [id_factura])
            row = await cur.fetchone()
            if row:
                adjunto_id, correo_id, xml_name = row
                
    msg = f"[PDF TRACE] Factura ID: {id_factura} -> adjunto_id: {adjunto_id}, correo_id: {correo_id}, XML Name: {xml_name}"
    logger.info(msg)
    print(msg, flush=True)

    if not correo_id:
        err_msg = f"[PDF TRACE] correo_id no encontrado para factura ID: {id_factura}"
        logger.warning(err_msg)
        print(err_msg, flush=True)
        return None

    # 2. Listar todos los adjuntos del mismo correo para ver si hay un PDF
    query_all_adjuntos = """
        SELECT adjunto_id, nombre_archivo, id_tipo_archivo, uri_almacenamiento
        FROM facturacion.adjuntos_correo
        WHERE correo_id = %s
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query_all_adjuntos, [correo_id])
            rows = await cur.fetchall()
            list_msg = f"[PDF TRACE] Adjuntos en DB para correo_id {correo_id}:"
            logger.info(list_msg)
            print(list_msg, flush=True)
            for r in rows:
                item_msg = f"  - ID: {r[0]}, Nombre: {r[1]}, Tipo: {r[2]} (1:ZIP, 2:XML, 3:PDF), S3 Key: {r[3]}"
                logger.info(item_msg)
                print(item_msg, flush=True)

    # 3. Buscar la S3 key del PDF
    query_pdf = """
        SELECT uri_almacenamiento
        FROM facturacion.adjuntos_correo
        WHERE id_tipo_archivo = 3 -- 3 = PDF
          AND correo_id = %s
        LIMIT 1
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query_pdf, [correo_id])
            row = await cur.fetchone()
            s3_key = row[0] if row else None
            res_msg = f"[PDF TRACE] S3 Key de PDF encontrado en DB: '{s3_key}'"
            logger.info(res_msg)
            print(res_msg, flush=True)
            return s3_key


async def obtener_pdf_factura(id_factura: int) -> tuple[bytes, str] | None:
    """Descarga el contenido PDF de una factura desde S3.

    Args:
        id_factura: ID de la factura.

    Returns:
        Tupla con (contenido_bytes, nombre_archivo) o None si no existe.
    """
    from config import get_aws_config
    aws_cfg = get_aws_config()
    bucket = aws_cfg.get('bucket_name')

    s3_key = await obtener_pdf_s3_key(id_factura)
    if not s3_key:
        err_msg = f"[PDF TRACE] No se encontró la llave S3 del PDF para la factura ID {id_factura}"
        logger.warning(err_msg)
        print(err_msg, flush=True)
        return None

    fetch_msg = f"[PDF TRACE] Descargando de S3 -> Bucket: '{bucket}', Key: '{s3_key}'"
    logger.info(fetch_msg)
    print(fetch_msg, flush=True)

    # Reutilizar el servicio de control para descargar desde S3
    from core.python.services import control_service
    contenido = await control_service.obtener_xml_factura(s3_key)

    if not contenido:
        fail_msg = f"[PDF TRACE] El contenido descargado de S3 fue nulo para Key: '{s3_key}'"
        logger.warning(fail_msg)
        print(fail_msg, flush=True)
        return None

    filename = s3_key.split('/')[-1]
    success_msg = f"[PDF TRACE] Descarga exitosa de S3 para '{filename}'"
    logger.info(success_msg)
    print(success_msg, flush=True)
    return contenido, filename


async def obtener_xml_s3_key(id_factura: int) -> str | None:
    """Busca la llave S3 del XML asociado a una factura.

    Args:
        id_factura: ID de la factura.

    Returns:
        Ruta del archivo XML en S3 o None si no se encuentra.
    """
    pool = get_pool()
    query_xml = """
        SELECT ac.uri_almacenamiento
        FROM facturacion.factura f
        LEFT JOIN facturacion.adjuntos_correo ac ON f.adjunto_id = ac.adjunto_id
        WHERE f.id_factura = %s
    """
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query_xml, [id_factura])
            row = await cur.fetchone()
            s3_key = row[0] if row else None
            res_msg = f"[XML TRACE] S3 Key de XML encontrado en DB para factura ID {id_factura}: '{s3_key}'"
            logger.info(res_msg)
            print(res_msg, flush=True)
            return s3_key


async def obtener_xml_factura_by_id(id_factura: int) -> tuple[bytes, str] | None:
    """Descarga el contenido XML de una factura desde S3 usando su ID de base de datos.

    Args:
        id_factura: ID de la factura.

    Returns:
        Tupla con (contenido_bytes, nombre_archivo) o None si no existe.
    """
    from config import get_aws_config
    aws_cfg = get_aws_config()
    bucket = aws_cfg.get('bucket_name')

    s3_key = await obtener_xml_s3_key(id_factura)
    if not s3_key:
        err_msg = f"[XML TRACE] No se encontró la llave S3 del XML para la factura ID {id_factura}"
        logger.warning(err_msg)
        print(err_msg, flush=True)
        return None

    fetch_msg = f"[XML TRACE] Descargando XML de S3 -> Bucket: '{bucket}', Key: '{s3_key}'"
    logger.info(fetch_msg)
    print(fetch_msg, flush=True)

    # Reutilizar el servicio de control para descargar desde S3
    from core.python.services import control_service
    contenido = await control_service.obtener_xml_factura(s3_key)

    if not contenido:
        fail_msg = f"[XML TRACE] El contenido descargado de S3 fue nulo para Key: '{s3_key}'"
        logger.warning(fail_msg)
        print(fail_msg, flush=True)
        return None

    filename = s3_key.split('/')[-1]
    success_msg = f"[XML TRACE] Descarga exitosa de S3 para XML '{filename}'"
    logger.info(success_msg)
    print(success_msg, flush=True)
    return contenido, filename


async def actualizar_verificacion_grafica(id_factura: int, aprobado: bool) -> bool:
    """Actualiza el estado de la verificación gráfica de una factura de forma manual."""
    pool = get_pool()
    estado_grafico = 'APROBADA' if aprobado else 'RECHAZADA'
    estado_factura = 3 if aprobado else 4  # 3 = PROCESADO, 4 = ERROR (Rechazada)
    estado_proceso = 3 if aprobado else 4

    query_get_adjunto = """
        SELECT adjunto_id 
        FROM facturacion.factura 
        WHERE id_factura = %s
    """
    
    query_update_factura = """
        UPDATE facturacion.factura 
        SET verificacion_grafica_estado = %s, 
            id_estado_proceso = %s,
            fecha_actualizacion = NOW()
        WHERE id_factura = %s
    """

    query_update_proceso = """
        UPDATE facturacion.proceso_ingesta 
        SET id_estado = %s, 
            observacion = %s,
            fecha_fin = NOW()
        WHERE adjunto_id = %s AND id_proceso = 25
    """

    query_resolve_alerta = """
        UPDATE facturacion.alerta 
        SET resuelta = TRUE, 
            fecha_resolucion = NOW()
        WHERE factura_id = %s AND codigo_tipo_alerta = 'VERIFICACION_GRAFICA_FALLIDA'
    """

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query_get_adjunto, [id_factura])
            row = await cur.fetchone()
            if not row:
                return False
            adjunto_id = row[0]

            await cur.execute(query_update_factura, [estado_grafico, estado_factura, id_factura])

            obs_proceso = 'Verificacion grafica aprobada manualmente por el usuario.' if aprobado else 'Verificacion grafica rechazada manualmente por el usuario.'
            await cur.execute(query_update_proceso, [estado_proceso, obs_proceso, adjunto_id])
            if cur.rowcount == 0:
                query_insert_proceso = """
                    INSERT INTO facturacion.proceso_ingesta 
                    (adjunto_id, id_proceso, id_estado, observacion, fecha_inicio, fecha_fin)
                    VALUES (%s, 25, %s, %s, NOW(), NOW())
                """
                await cur.execute(query_insert_proceso, [adjunto_id, estado_proceso, obs_proceso])

            await cur.execute(query_resolve_alerta, [id_factura])
            
            return True



