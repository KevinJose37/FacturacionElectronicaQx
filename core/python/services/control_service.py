"""Servicio de consultas y actualización para la página de control de facturas."""

import calendar
import logging
from datetime import date

from config import load_yaml_queries
from core.python.db import get_pool
from utils.s3_utils import obtener_xml_s3

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('control/queries_control.yml')


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
            's3_key': r[14] or '',
            'id_factura': r[15],
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


async def obtener_paquete_factura(id_factura: int) -> tuple[bytes, str] | None:
    """Obtiene los archivos de la factura comprimidos en un ZIP.

    Busca el ZIP original en S3. Si no existe, descarga los archivos PDF y XML
    asociados y los comprime en un nuevo archivo ZIP.

    Args:
        id_factura: Identificador de la factura en la base de datos.

    Returns:
        Tupla con (contenido_zip_bytes, nombre_archivo) o None si falla.
    """
    import io
    import zipfile

    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    from config import get_aws_config

    pool = get_pool()
    aws_cfg = get_aws_config()
    bucket = aws_cfg.get('bucket_name')

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # 1. Obtener número de factura y lista de adjuntos de la familia
            await cur.execute(
                'SELECT numero_factura FROM facturacion.factura WHERE id_factura = %s',
                (id_factura,),
            )
            row_factura = await cur.fetchone()
            if not row_factura:
                return None
            nombre_factura = row_factura[0]

            await cur.execute(_QUERIES['obtener_adjuntos'], (id_factura,))
            adjuntos = await cur.fetchall()

    if not adjuntos:
        return None

    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_cfg.get('access_key'),
        aws_secret_access_key=aws_cfg.get('secret_key'),
        region_name=aws_cfg.get('region_name'),
    )

    # Identificar el ZIP original si existe
    zip_original = next((a for a in adjuntos if a[1] == 1), None)

    if zip_original:
        try:
            response = s3_client.get_object(Bucket=bucket, Key=zip_original[0])
            contenido = response['Body'].read()
            return contenido, f'{nombre_factura}.zip'
        except (BotoCoreError, ClientError) as e:
            logger.warning('ZIP original no accesible en S3 (%s): %s', zip_original[0], e)

    # Si no hay ZIP o falló su descarga, comprimir PDF y XML
    buffer = io.BytesIO()
    con_archivos = False

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for uri, tipo, nombre in adjuntos:
            if tipo not in (2, 3):  # Solo XML (2) y PDF (3)
                continue
            try:
                response = s3_client.get_object(Bucket=bucket, Key=uri)
                zf.writestr(nombre, response['Body'].read())
                con_archivos = True
            except (BotoCoreError, ClientError) as e:
                logger.error('Error descargando archivo %s de S3: %s', uri, e)

    if not con_archivos:
        return None

    buffer.seek(0)
    return buffer.getvalue(), f'{nombre_factura}.zip'


async def obtener_xml_factura(s3_key: str) -> bytes | None:
    """Descarga el contenido de un archivo XML desde S3.

    Args:
        s3_key: Ruta del archivo en el bucket S3.

    Returns:
        Contenido en bytes del archivo o None si falla.
    """
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    from config import get_aws_config

    aws_cfg = get_aws_config()
    resultado = None

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_cfg.get('access_key'),
            aws_secret_access_key=aws_cfg.get('secret_key'),
            region_name=aws_cfg.get('region_name'),
        )
        response = s3_client.get_object(
            Bucket=aws_cfg.get('bucket_name'),
            Key=s3_key,
        )
        resultado = response['Body'].read()
    except (BotoCoreError, ClientError) as e:
        logger.error('Error descargando XML desde S3 (%s): %s', s3_key, e)

    return resultado
