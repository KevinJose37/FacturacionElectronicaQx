"""Módulo para registrar procesos de ingesta en la base de datos.

Provee la función ``registrar_proceso_ingesta`` que inserta un registro
en ``FACTURACION.PROCESO_INGESTA`` usando una conexión síncrona (psycopg2).
"""

import logging
from datetime import datetime

from config import (
    create_postgres_connection,
    get_postgres_config,
    load_yaml_queries,
)
from metadata.log_proceso_metadata import MensajesLogProceso

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('log_proceso/queries_log_proceso.yml')


def registrar_proceso_ingesta(
    id_estado_proceso: int,
    observaciones: str,
    fecha_inicio: datetime,
    correo_id: int | None = None,
) -> int:
    """Registra un nuevo proceso de ingesta en la base de datos.

    Inserta un registro en FACTURACION.PROCESO_INGESTA con el estado,
    la observación y la fecha de inicio proporcionados. La fecha de fin
    se asigna automáticamente con NOW() al momento de la inserción.

    Args:
        id_estado_proceso:
            ID del estado del proceso (referencia a TIPO_ESTADO_PROCESO).
        observaciones:
            Mensaje personalizado que describe la etapa o resultado del proceso.
        fecha_inicio:
            Timestamp que marca el inicio del proceso que se está registrando.
        correo_id:
            ID del correo asociado (referencia a CORREO_ENTRANTE). Opcional.

    Returns:
        El ID del proceso de ingesta recién creado.

    Raises:
        DatabaseError: Si ocurre un error al insertar el registro.
    """
    config = get_postgres_config()
    conexion = create_postgres_connection(config)
    query = _QUERIES.get('insertar')
    id_generado = None

    try:
        with conexion:
            with conexion.cursor() as cursor:
                cursor.execute(
                    query,
                    (correo_id, id_estado_proceso, observaciones, fecha_inicio),
                )
                fila = cursor.fetchone()
                id_generado = fila[0]
        logger.info(MensajesLogProceso.registro_exitoso, id_generado, observaciones[:80])

    except Exception as exc:
        logger.error(MensajesLogProceso.error_registro, exc)
        raise

    finally:
        conexion.close()

    return id_generado
