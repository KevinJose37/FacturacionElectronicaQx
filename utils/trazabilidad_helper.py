"""Funciones auxiliares para la gestión de trazabilidad en la base de datos."""

import logging
from typing import Any

from config import get_queries_trazabilidad
from utils.db_utils import ejecutar_consulta

logger = logging.getLogger(__name__)


def obtener_siguiente_secuencia(conexion: Any, id_proceso: int) -> int:
    """Calcula el siguiente número de secuencia para un proceso específico.

    Args:
        conexion: Conexión activa a PostgreSQL.
        id_proceso: ID del proceso en PROCESO_INGESTA.

    Returns:
        Siguiente número de secuencia disponible.
    """
    queries = get_queries_trazabilidad()
    query = queries.get('obtener_siguiente_secuencia')
    parametros = (id_proceso,)

    try:
        resultado = ejecutar_consulta(conexion, query, parametros)
        if resultado:
            secuencia = resultado[0].get('siguiente', 1)
        else:
            secuencia = 1
    except Exception as e:
        logger.warning(f'No se pudo obtener secuencia para proceso {id_proceso}: {e}')
        secuencia = 1

    return secuencia


def obtener_id_estado(conexion: Any, codigo_referencia: str) -> int:
    """Obtiene el ID de un estado a partir de su código de referencia.

    Args:
        conexion: Conexión activa a PostgreSQL.
        codigo_referencia: Código de referencia del estado (ej: 'RECIBIDO').

    Returns:
        ID del estado o 10 (ERROR) por defecto si no se encuentra.
    """
    queries = get_queries_trazabilidad()
    query = queries.get('obtener_id_estado')
    parametros = (codigo_referencia,)

    try:
        resultado = ejecutar_consulta(conexion, query, parametros)
        if resultado:
            id_estado = resultado[0].get('id_estado_proceso', 10)
        else:
            logger.warning(f'Estado no encontrado: {codigo_referencia}')
            id_estado = 10
    except Exception as e:
        logger.error(f'Error consultando estado {codigo_referencia}: {e}')
        id_estado = 10

    return id_estado
