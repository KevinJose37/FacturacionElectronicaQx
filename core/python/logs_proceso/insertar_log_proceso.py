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
    adjunto_id: int,
    id_estado: int,
    id_proceso: int,
    observacion: str,
    fecha_inicio: datetime,
    id_error: int | None = None,
) -> int:
    """Registra un nuevo proceso de ingesta en la base de datos.

    Inserta un registro en FACTURACION.PROCESO_INGESTA con la totalidad de
    sus campos correspondientes al modelo de datos actual. El único campo
    que permite nulos es id_error.

    Args:
        adjunto_id:
            ID del adjunto asociado (referencia a ADJUNTOS_CORREO).
        id_estado:
            ID del estado del proceso (referencia a TIPO_ESTADO_PROCESO).
        id_proceso:
            ID de proceso desde otras tablas (Obligatorio).
        observacion:
            Mensaje personalizado que describe la etapa o resultado del proceso (Obligatorio).
        fecha_inicio:
            Timestamp que marca el inicio del proceso (Obligatorio).
        id_error:
            ID de error desde tabla de errores (Opcional, puede ser null).

    Returns:
        El ID del proceso de ingesta recién creado (ID_PROCESO_INGESTA).

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
                    (adjunto_id, id_proceso, id_estado, id_error, observacion, fecha_inicio),
                )
                fila = cursor.fetchone()
                id_generado = fila[0]
        
        obs_log = observacion[:80] if observacion else "Sin observaciones"
        logger.info(MensajesLogProceso.registro_exitoso, id_generado, obs_log)

    except Exception as exc:
        logger.error(MensajesLogProceso.error_registro, exc)
        raise

    finally:
        conexion.close()

    return id_generado
