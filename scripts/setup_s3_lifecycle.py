"""Script para configurar políticas de ciclo de vida (Lifecycle) en el bucket S3.

Esta política asegura el cumplimiento de retención (Habeas Data / Normativa Contable),
moviendo los adjuntos (XML y PDF) a almacenamiento Glacier después de 5 años, 
y eliminándolos de forma definitiva y segura después de 10 años (3650 días).
"""

import logging
import boto3
from botocore.exceptions import ClientError
from config import get_aws_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def configurar_ciclo_vida_s3() -> None:
    """Aplica la regla de Lifecycle al bucket principal."""
    aws_cfg = get_aws_config()
    bucket_name = aws_cfg.get('bucket_name')
    
    if not bucket_name:
        logger.error("No se encontró el nombre del bucket en la configuración.")
        return

    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_cfg.get('access_key'),
        aws_secret_access_key=aws_cfg.get('secret_key'),
        region_name=aws_cfg.get('region_name')
    )

    # 10 años (aproximado)
    DIAS_RETIRO = 3650
    # 5 años (aproximado)
    DIAS_GLACIER = 1825

    lifecycle_config = {
        'Rules': [
            {
                'ID': 'RetencionHabeasDataContable',
                'Status': 'Enabled',
                'Filter': {
                    'Prefix': '' # Aplica a todo el bucket
                },
                'Transitions': [
                    {
                        'Days': DIAS_GLACIER,
                        'StorageClass': 'GLACIER'
                    }
                ],
                'Expiration': {
                    'Days': DIAS_RETIRO
                }
            }
        ]
    }

    try:
        s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration=lifecycle_config
        )
        logger.info(f"Política de ciclo de vida (10 años retención) aplicada al bucket '{bucket_name}'.")
    except ClientError as e:
        logger.error(f"Error al configurar Lifecycle en el bucket '{bucket_name}': {e}")

if __name__ == '__main__':
    configurar_ciclo_vida_s3()
