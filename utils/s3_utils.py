"""Utilidades para la interacción con Amazon S3.

Maneja la subida y descarga segura de archivos de S3.
"""

import logging
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from lxml import etree

from config import get_aws_config


logger = logging.getLogger(__name__)


def subir_archivo_s3(
    ruta_local: Path | str,
    destino_s3: str,
    bucket_name: str | None = None,
) -> bool:
    """Sube un archivo local a un bucket de Amazon S3.

    Args:
        ruta_local: Ruta absoluta o relativa al archivo local que se desea subir.
        destino_s3: Ruta o llave (Key) dentro del bucket donde se almacenará el archivo.
        bucket_name: Nombre del bucket de S3.

    Returns:
        True si la subida fue exitosa, False si ocurrió algún error.
    """
    ruta = Path(ruta_local)
    es_exitoso = False

    if not ruta.exists() or not ruta.is_file():
        logger.error(f'El archivo local no existe: {ruta_local}')
    else:
        aws_cfg = get_aws_config()
        target_bucket = bucket_name or aws_cfg.get('bucket_name')

        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_cfg.get('access_key'),
                aws_secret_access_key=aws_cfg.get('secret_key'),
                region_name=aws_cfg.get('region_name')
            )
            s3_client.upload_file(
                str(ruta), 
                target_bucket, 
                destino_s3,
                ExtraArgs={'ServerSideEncryption': 'AES256'}
            )
            es_exitoso = True
        except (BotoCoreError, ClientError) as error:
            logger.error(f'Error de AWS al subir el archivo {ruta_local} a S3: {error}')
        except Exception as e:
            logger.error(f'Error inesperado al subir a S3: {e}')

    return es_exitoso


def copiar_archivo_s3(
    origen_key: str,
    destino_key: str,
    bucket_name: str | None = None,
    bucket_origen: str | None = None,
) -> bool:
    """Copia un objeto dentro de S3 (server-side, sin pasar por el cliente).

    Útil para mover/duplicar archivos ya almacenados en el bucket sin
    necesidad de descargarlos y volverlos a subir.

    Args:
        origen_key: Key del objeto fuente dentro del bucket de origen.
        destino_key: Key destino dentro del bucket de destino.
        bucket_name: Bucket de destino. Si es None, usa el de configuración.
        bucket_origen: Bucket de origen. Si es None, usa el mismo destino.

    Returns:
        True si la copia fue exitosa, False si ocurrió algún error.
    """
    es_exitoso = False
    aws_cfg = get_aws_config()
    target_bucket = bucket_name or aws_cfg.get('bucket_name')
    source_bucket = bucket_origen or target_bucket

    if not origen_key or not destino_key:
        logger.error('copiar_archivo_s3: origen_key o destino_key vacíos.')
        return False

    if origen_key == destino_key and source_bucket == target_bucket:
        logger.debug('Origen y destino idénticos, omitiendo copia: %s', origen_key)
        return True

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_cfg.get('access_key'),
            aws_secret_access_key=aws_cfg.get('secret_key'),
            region_name=aws_cfg.get('region_name')
        )
        s3_client.copy_object(
            Bucket=target_bucket,
            Key=destino_key,
            CopySource={'Bucket': source_bucket, 'Key': origen_key},
            ServerSideEncryption='AES256'
        )
        es_exitoso = True
    except (BotoCoreError, ClientError) as error:
        logger.error(
            'Error de AWS al copiar s3://%s/%s -> s3://%s/%s: %s',
            source_bucket, origen_key, target_bucket, destino_key, error,
        )
    except Exception as e:
        logger.error('Error inesperado al copiar en S3: %s', e)

    return es_exitoso


def descargar_archivo_s3(
    s3_key: str,
    ruta_local: Path | str,
    bucket_name: str | None = None,
) -> bool:
    """Descarga un archivo desde S3 a una ruta local.

    Args:
        s3_key: Llave (Key) del objeto en S3.
        ruta_local: Ruta destino en el sistema de archivos local.
        bucket_name: Nombre del bucket. Si es None, usa el de configuración.

    Returns:
        True si la descarga fue exitosa, False de lo contrario.
    """
    es_exitoso = False
    aws_cfg = get_aws_config()
    target_bucket = bucket_name or aws_cfg.get('bucket_name')

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_cfg.get('access_key'),
            aws_secret_access_key=aws_cfg.get('secret_key'),
            region_name=aws_cfg.get('region_name')
        )
        s3_client.download_file(target_bucket, s3_key, str(ruta_local))
        es_exitoso = True
    except (BotoCoreError, ClientError) as error:
        logger.error(f'Error de AWS al descargar s3://{target_bucket}/{s3_key}: {error}')
    except Exception as e:
        logger.error(f'Error inesperado al descargar de S3: {e}')

    return es_exitoso


def obtener_xml_s3(
    s3_key: str,
    bucket_name: str | None = None,
    aws_credentials: dict | None = None,
) -> Any:
    """Descarga y parsea un archivo XML desde un bucket de Amazon S3.

    Args:
        s3_key: Ruta o llave (Key) del archivo XML dentro del bucket.
        bucket_name: Nombre del bucket. Si es None, usa el de configuración.
        aws_credentials: Diccionario con credenciales (access_key, secret_key, region).

    Returns:
        Objeto Element raíz de lxml si fue exitoso, None en caso de error.
    """
    arbol_xml = None
    aws_cfg = aws_credentials or get_aws_config()
    target_bucket = bucket_name or aws_cfg.get('bucket_name')

    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_cfg.get('access_key'),
            aws_secret_access_key=aws_cfg.get('secret_key'),
            region_name=aws_cfg.get('region_name')
        )
        respuesta = s3_client.get_object(Bucket=target_bucket, Key=s3_key)
        contenido_bytes = respuesta['Body'].read()
        arbol_xml = etree.fromstring(contenido_bytes)
    except (BotoCoreError, ClientError) as error:
        logger.error(f'Error de AWS al obtener s3://{target_bucket}/{s3_key}: {error}')
    except etree.XMLSyntaxError as error:
        logger.error(f'Error de sintaxis XML en s3://{target_bucket}/{s3_key}: {error}')
    except Exception as e:
        logger.error(f'Error inesperado al obtener XML de S3: {e}')

    return arbol_xml
