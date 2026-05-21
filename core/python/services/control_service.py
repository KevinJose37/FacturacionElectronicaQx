"""Servicio de consultas y actualización para la página de control de facturas."""

import calendar
import io
import logging
import zipfile
from datetime import date
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config import get_aws_config, load_yaml_queries
from core.python.db import get_pool

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('control/queries_control.yml').get('control', {})



async def listar_control(
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    page: int = 1,
    size: int = 20,
    busqueda: str | None = None,
) -> dict:
    """Lista registros de control de facturas con paginación y filtros.

    Args:
        fecha_inicio: Fecha inicial del rango de consulta.
        fecha_fin: Fecha final del rango de consulta.
        page: Número de página (1-indexed).
        size: Cantidad de registros por página.
        busqueda: Filtro opcional por tipo de alerta/evento.

    Returns:
        Diccionario con items paginados y metadata de paginación.
    """
    pool = get_pool()

    if not fecha_inicio or not fecha_fin:
        # Si hay búsqueda, ampliamos el rango de fechas para encontrar los registros
        if busqueda:
            fecha_inicio = date(2000, 1, 1)
            fecha_fin = date(2100, 12, 31)
        else:
            hoy = date.today()
            fecha_inicio = hoy.replace(day=1)
            ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
            fecha_fin = hoy.replace(day=ultimo_dia)

    offset = (page - 1) * size

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                _QUERIES['contar'],
                [fecha_inicio, fecha_fin, busqueda, busqueda, busqueda, busqueda, busqueda],
            )
            total_records = (await cur.fetchone())[0]

            await cur.execute(
                _QUERIES['listar'],
                [fecha_inicio, fecha_fin, busqueda, busqueda, busqueda, busqueda, busqueda, size, offset],
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
            'aceptacion_expresa': bool(r[11]),
            'observaciones_entrega': r[12] or '',
            's3_key': r[13] or '',
            'id_factura': r[14],
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
        datos.get('aceptacion_expresa', False),
        datos.get('observaciones_entrega'),
        id_control,
    ]

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['actualizar'], params)
            filas_afectadas = cur.rowcount
        await conn.commit()

    resultado = filas_afectadas > 0
    return resultado


async def obtener_paquete_factura(id_factura_o_referencia: Any) -> tuple | None:
    """Obtiene los archivos de la factura comprimidos en un ZIP.

    Busca la factura por su ID interno o por su número de factura.

    Args:
        id_factura_o_referencia: ID técnico o número alfanumérico de factura.

    Returns:
        Tupla con (contenido_bytes, nombre_archivo) o None si falla.
    """
    aws_cfg = get_aws_config()
    bucket = aws_cfg.get('bucket_name')
    pool = get_pool()
    paquete = None

    try:
        # Limpiar y normalizar la referencia recibida
        ref_str = str(id_factura_o_referencia).strip()

        # Intentar convertir a int para búsqueda por ID técnico
        try:
            ref_int = int(ref_str)
        except (ValueError, TypeError):
            ref_int = -1

        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Validar existencia de la factura (ID, Número exacto o Prefijo+Número)
                logger.info(f'Buscando factura con referencia: {ref_str}')
                await cur.execute(
                    '''
                    SELECT id_factura, numero_factura
                    FROM facturacion.factura
                    WHERE id_factura = %s
                       OR numero_factura = %s
                       OR (prefijo_facturacion || numero_factura) = %s
                    LIMIT 1
                    ''',
                    (ref_int, ref_str, ref_str),
                )
                row_factura = await cur.fetchone()

                if not row_factura:
                    logger.error(f'FACTURA NO ENCONTRADA: {ref_str}')
                    return None

                id_factura_real, nombre_factura = row_factura
                logger.info(f'Factura identificada: {nombre_factura} (ID Interno: {id_factura_real})')

                # 2. Obtener adjuntos usando el ID real
                await cur.execute(_QUERIES['obtener_adjuntos'], (id_factura_real,))
                adjuntos = await cur.fetchall()

                if not adjuntos:
                    logger.error(f'SIN ADJUNTOS EN BD PARA FACTURA: {nombre_factura} (ID: {id_factura_real})')
                    return None

        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_cfg.get('access_key'),
            aws_secret_access_key=aws_cfg.get('secret_key'),
            region_name=aws_cfg.get('region_name'),
        )

        # 3. Buscar ZIP original (Tipo 1)
        zip_original = next((a for a in adjuntos if a[1] == 1), None)
        if zip_original:
            try:
                logger.info(f'Descargando ZIP original de S3: {zip_original[0]}')
                response = s3_client.get_object(Bucket=bucket, Key=zip_original[0])
                contenido_raw = response['Body'].read()
                paquete = (contenido_raw, f'{nombre_factura}.zip')
            except Exception as e:
                logger.warning(f'Fallo al obtener ZIP original ({zip_original[0]}), intentando con archivos sueltos: {e}')

        # 4. Comprimir XML (2) y PDF (3) si no se obtuvo el ZIP original
        if not paquete:
            buffer = io.BytesIO()
            con_archivos = False

            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for uri, tipo, nombre in adjuntos:
                    if tipo in (2, 3):
                        try:
                            logger.info(f'Comprimiendo archivo de S3: {uri}')
                            response = s3_client.get_object(Bucket=bucket, Key=uri)
                            zf.writestr(nombre, response['Body'].read())
                            con_archivos = True
                        except Exception as e:
                            logger.error(f'Error descargando adjunto {uri}: {e}')

            if con_archivos:
                buffer.seek(0)
                paquete = (buffer.getvalue(), f'{nombre_factura}.zip')

    except Exception as e:
        logger.exception(f'Error inesperado en obtener_paquete_factura: {e}')

    return paquete


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
