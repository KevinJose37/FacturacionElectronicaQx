"""Lógica principal para el registro de trazabilidad en los procesos de facturación."""

import json
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
    detalle_error: str | None = None,
    marcar_fin: bool = False,
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
        logger.error("No se pudo establecer conexión para registrar log.")
        return None

    secuencia = obtener_siguiente_secuencia(conexion, id_proceso)
    id_estado = obtener_id_estado(conexion, codigo_estado)

    datos_log = {
        "id_proceso": id_proceso,
        "numero_secuencia": secuencia,
        "codigo_etapa": codigo_etapa,
        "id_estado_proceso": id_estado,
        "detalle_json": json.dumps(detalle_json) if detalle_json is not None else None,
        "detalle_error": detalle_error,
    }

    if marcar_fin:
        from datetime import datetime
        datos_log["fecha_fin"] = datetime.now()

    try:
        id_log = insertar_datos(
            conexion=conexion,
            esquema="facturacion",
            tabla="log_proceso",
            datos=datos_log,
        )
        logger.info(f"Log registrado: Proceso {id_proceso}, Etapa {codigo_etapa}")
    except Exception as e:
        logger.error(f"Error al registrar log de trazabilidad: {e}")
        id_log = None
    finally:
        conexion.close()

    return id_log

def iniciar_proceso_ingesta(codigo_estado: str) -> int | None:
    """Inicia un nuevo proceso de ingesta en la base de datos.
    
    Args:
        codigo_estado: Código de referencia del estado inicial (ej: 'RECIBIDO').
        
    Returns:
        El ID del proceso generado o None si falló.
    """
    id_proceso_generado = None
    
    try:
        conexion = obtener_conexion()
    except Exception as e:
        logger.error(f"No se pudo establecer conexión para iniciar proceso: {e}")
        conexion = None

    if conexion:
        try:
            id_estado = obtener_id_estado(conexion, codigo_estado)
            id_proceso_generado = insertar_datos(
                conexion=conexion,
                esquema="facturacion",
                tabla="proceso_ingesta",
                datos={"id_estado_proceso": id_estado}
            )
            logger.info(f"Proceso de ingesta iniciado con ID: {id_proceso_generado}")
        except Exception as e:
            logger.error(f"Error al iniciar proceso de ingesta: {e}")
        finally:
            conexion.close()
            
    return id_proceso_generado
