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
        verif_graf_estado = r[12] or ''
        if verif_graf_estado == 'PENDIENTE':
            estado_txt = 'pendiente_verificacion_manual'

        resultado.append({
            'id': r[0],
            'db_id': r[4],
            'provider': r[1] or DefaultTextos.sin_nombre,
            'type': DefaultTextos.factura_electronica,
            'status': estado_txt,
            'amount': float(r[3]) if r[3] is not None else 0.0,
            'date': r[5].strftime(DefaultTextos.formato_fecha_corto) if r[5] else '',
            'time': '1.2s',
            'motivo_rechazo_xml': r[10] or '',
            'motivo_rechazo_pdf': r[11] or '',
            'verificacion_grafica_estado': verif_graf_estado,
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
        'pendientes_verificacion_manual': row[5] if len(row) > 5 else 0,
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


async def obtener_detalle_verificacion(id_factura: int) -> dict | None:
    """Obtiene el detalle de verificación gráfica y datos XML clave para la revisión manual.

    Devuelve los 13 campos que corresponden a los numerales 1-5, 8-13, 15 y 18
    del artículo 11 de la Resolución 000165 de 2023.

    Args:
        id_factura: ID de la factura.

    Returns:
        Diccionario con verificacion_ia (resultado IA campo por campo) y datos_xml (campos clave).
    """
    import json as _json
    pool = get_pool()
    query = """
        SELECT 
            f.verificacion_grafica_detalle,
            f.verificacion_grafica_estado,
            f.numero_factura,
            f.prefijo_facturacion,
            f.razon_social_emisor,
            emisor.numero_documento as nit_emisor,
            f.razon_social_adquiriente,
            adq.numero_documento as nit_adquiriente,
            f.valor_total,
            f.cufe,
            f.fecha_expedicion,
            f.denominacion,
            auth.numero_resolucion as resolucion_dian,
            (SELECT codigo_forma_pago FROM facturacion.pago_factura WHERE id_factura = f.id_factura LIMIT 1) as forma_pago,
            (SELECT SUM(valor_impuesto) FROM facturacion.impuesto_factura WHERE id_factura = f.id_factura AND codigo_impuesto = '01') as iva,
            f.contenido_qr,
            f.fecha_generacion,
            (SELECT STRING_AGG(df.descripcion_item, '; ' ORDER BY df.numero_linea)
             FROM facturacion.detalle_factura df WHERE df.id_factura = f.id_factura) as descripcion_items,
            (SELECT COALESCE(
                (SELECT pt.razon_social FROM facturacion.proveedor_tecnologico pt WHERE pt.nit_proveedor = fs.numero_documento),
                CASE WHEN fs.razon_social IN ('31', '6', '13', '21', '22', '41', '42') THEN 'Proveedor Tecnológico (' || fs.numero_documento || ')' ELSE fs.razon_social END
             )
             FROM facturacion.software_factura sf
             JOIN facturacion.producto_software ps ON sf.id_producto_software = ps.id_producto_software
             JOIN facturacion.fabricante_software fs ON ps.id_fabricante_software = fs.id_fabricante_software
             WHERE sf.id_factura = f.id_factura LIMIT 1) as fabricante_software,
            (SELECT ps.nombre_software
             FROM facturacion.software_factura sf
             JOIN facturacion.producto_software ps ON sf.id_producto_software = ps.id_producto_software
             WHERE sf.id_factura = f.id_factura LIMIT 1) as nombre_software
        FROM facturacion.factura f
        LEFT JOIN facturacion.tercero emisor ON f.id_tercero_emisor = emisor.id_tercero
        LEFT JOIN facturacion.tercero adq ON f.id_tercero_adquiriente = adq.id_tercero
        LEFT JOIN facturacion.autorizacion_numeracion_dian auth ON f.id_autorizacion = auth.id_autorizacion
        WHERE f.id_factura = %s
    """
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, [id_factura])
                row = await cur.fetchone()
                if not row:
                    return None

                detalle_raw = row[0]
                verificacion_ia = {}
                if detalle_raw:
                    # Guardia contra la multi-serialización de cadenas JSON
                    parsed = detalle_raw
                    for _ in range(5):
                        if isinstance(parsed, str):
                            try:
                                parsed = _json.loads(parsed)
                            except _json.JSONDecodeError:
                                break
                        else:
                            break
                    if isinstance(parsed, dict):
                        verificacion_ia = parsed

                # Mapear código de forma de pago a texto legible
                _FORMAS_PAGO = {'1': 'Contado', '2': 'Crédito'}
                codigo_forma_pago = str(row[13]).strip() if row[13] else ''
                forma_pago_texto = _FORMAS_PAGO.get(codigo_forma_pago, codigo_forma_pago)

                # Formatear fecha/hora de generación
                fecha_hora_gen = ''
                if row[16]:
                    fecha_hora_gen = row[16].strftime('%Y-%m-%d %H:%M:%S')

                import re as _re
                fabricante_software = row[18] or ''
                nombre_software = row[19] or ''

                uuid_pattern = _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', _re.IGNORECASE)
                if uuid_pattern.match(nombre_software.strip()):
                    short_uuid = nombre_software.strip().split('-')[0]
                    fabricante_clean = fabricante_software.split(' / ')[0] if fabricante_software else 'Proveedor'
                    nombre_software = f"Software de {fabricante_clean} ({short_uuid})"

                datos_xml = {
                    'razon_social_emisor': row[4] or '',
                    'nit_emisor': row[5] or '',
                    'razon_social_adquiriente': row[6] or '',
                    'nit_adquiriente': row[7] or '',
                    'numero_factura': row[2] or '',
                    'fecha_expedicion': row[10].strftime('%Y-%m-%d') if row[10] else '',
                    'descripcion_items': row[17] or '',
                    'valor_total': str(row[8]) if row[8] is not None else '',
                    'iva': str(row[14]) if row[14] is not None else '',
                    'cufe': row[9] or '',
                    'contenido_qr': row[15] or '',
                    'fabricante_software': fabricante_software,
                    'nombre_software': nombre_software,
                    'fecha_hora_generacion': fecha_hora_gen,
                    'forma_pago': forma_pago_texto,
                    'denominacion': row[11] or '',
                    'resolucion_dian': row[12] or '',
                    'prefijo_facturacion': row[3] or '',
                }

                return {
                    'verificacion_ia': verificacion_ia,
                    'verificacion_estado': row[1] or 'PENDIENTE',
                    'datos_xml': datos_xml,
                }
    except Exception as e:
        logger.error("Error obteniendo detalle de verificación: %s", e)
        return None


async def actualizar_verificacion_grafica(
    id_factura: int,
    aprobado: bool,
    motivos_rechazo: list[str] | None = None,
) -> bool:
    """Actualiza el estado de la verificación gráfica de una factura de forma manual."""
    pool = get_pool()
    estado_grafico = 'APROBADA' if aprobado else 'RECHAZADA'
    estado_factura = 3 if aprobado else 4  # 3 = PROCESADO, 4 = ERROR (Rechazada)
    estado_proceso = 3 if aprobado else 4

    # Build motivo_rechazo string from the selected numerals
    motivo_rechazo_texto = None
    if not aprobado and motivos_rechazo:
        motivo_rechazo_texto = 'Rechazo manual – Incumplimiento representación gráfica: ' + '; '.join(motivos_rechazo)

    query_get_adjunto = """
        SELECT adjunto_id 
        FROM facturacion.factura 
        WHERE id_factura = %s
    """
    
    query_update_factura = """
        UPDATE facturacion.factura 
        SET verificacion_grafica_estado = %s, 
            id_estado_proceso = %s,
            motivo_rechazo = COALESCE(%s, motivo_rechazo),
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

            await cur.execute(query_update_factura, [estado_grafico, estado_factura, motivo_rechazo_texto, id_factura])

            obs_proceso = 'Verificacion grafica aprobada manualmente por el usuario.' if aprobado else 'Verificacion grafica rechazada manualmente por el usuario.'
            if motivo_rechazo_texto:
                obs_proceso = motivo_rechazo_texto
            
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
