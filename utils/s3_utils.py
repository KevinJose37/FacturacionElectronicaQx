"""Utilidades para la interacción con Amazon S3.
Maneja la subida segura de archivos a los buckets de S3 configurados."""

import logging
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

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
        logger.error(f"El archivo local no existe: {ruta_local}")
    else:
        aws_cfg = get_aws_config()
        target_bucket = bucket_name or aws_cfg.get('bucket_name')

        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=aws_cfg.get('access_key'),
                aws_secret_access_key=aws_cfg.get('secret_key')
            )
            s3_client.upload_file(str(ruta), target_bucket, destino_s3)
            logger.info(
                f"Archivo subido a S3 exitosamente: s3://{target_bucket}/{destino_s3}"
            )
            es_exitoso = True
        except (BotoCoreError, ClientError) as error:
            logger.error(f"Error de AWS al subir el archivo {ruta_local} a S3: {error}")
        except Exception as e:
            logger.error(f"Error inesperado al subir a S3: {e}")

    return es_exitoso

