"""Lógica principal para el registro de trazabilidad en los procesos de facturación."""

import logging
from typing import Any

from utils.db_utils import insertar_datos, obtener_conexion
from utils.trazabilidad_helper import obtener_id_estado, obtener_siguiente_secuencia

logger = logging.getLogger(__name__)


def registrar_log_etapa(
    id_proceso: int,
    codigo_etapa: str,
    codigo_estado: str,
    detalle_json: dict | None = None,
    detalle_error: str | None = None
) -> int | None:
    """Registra un nuevo evento de log en la trazabilidad del proceso.

    Args:
        id_proceso: ID del proceso en PROCESO_INGESTA.
        codigo_etapa: Código técnico de la etapa (de EtapasProceso).
        codigo_estado: Código de referencia del estado (ej: 'RECIBIDO').
        detalle_json: Diccionario con información técnica adicional.
        detalle_error: Descripción del error si la etapa falló.

    Returns:
        ID del log generado o None si falló el registro.
    """
    conexion = obtener_conexion()
    if not conexion:
        logger.error('No se pudo establecer conexión para registrar log.')
        return None

    secuencia = obtener_siguiente_secuencia(conexion, id_proceso)
    id_estado = obtener_id_estado(conexion, codigo_estado)

    datos_log = {
        'ID_PROCESO': id_proceso,
        'NUMERO_SECUENCIA': secuencia,
        'CODIGO_ETAPA': codigo_etapa,
        'ID_ESTADO_PROCESO': id_estado,
        'DETALLE_JSON': detalle_json,
        'DETALLE_ERROR': detalle_error
    }

    try:
        id_log = insertar_datos(
            conexion=conexion,
            esquema='FACTURACION',
            tabla='LOG_PROCESO',
            datos=datos_log
        )
        logger.info(f'Log registrado: Proceso {id_proceso}, Etapa {codigo_etapa}')
    except Exception as e:
        logger.error(f'Error al registrar log de trazabilidad: {e}')
        id_log = None
    finally:
        conexion.close()

    return id_log
