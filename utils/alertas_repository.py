"""Repositorio síncrono para persistencia de alertas.

Encapsula las operaciones de base de datos para la tabla
FACTURACION.ALERTA. Usa conexiones síncronas (psycopg) porque
se invoca desde los flujos de ingesta y procesamiento que
también son síncronos.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import psycopg

from config import get_postgres_config
from metadata.alertas_metadata import (
    CodigoPrioridad,
    CodigoTipoAlerta,
    MensajesAlerta,
)

logger = logging.getLogger(__name__)


class AlertasRepository:
    """Repositorio para operaciones de persistencia de alertas."""

    def __init__(self, config: Optional[dict] = None):
        """Inicializa el repositorio.

        Args:
            config: Configuración de BD (si None, se lee de entorno).
        """
        self.config = config or get_postgres_config()

    def _get_connection(self) -> psycopg.Connection:
        """Crea una nueva conexión a la BD."""
        return psycopg.connect(
            host=self.config['host'],
            port=int(self.config['port']),
            dbname=self.config['dbname'],
            user=self.config['user'],
            password=self.config.get('password') or os.environ.get('POSTGRES_PASSWORD', ''),
        )

    def insertar_alerta(
        self,
        conn: Optional[psycopg.Connection],
        codigo_tipo: str,
        titulo: str,
        mensaje: str,
        codigo_prioridad: Optional[str] = None,
        contexto: Optional[dict] = None,
        correo_id: Optional[int] = None,
        adjunto_id: Optional[int] = None,
        factura_id: Optional[int] = None,
        correo_enviado: bool = False,
    ) -> int:
        """Inserta una alerta en FACTURACION.ALERTA.

        Args:
            conn: Conexión activa. Si None, crea una propia.
            codigo_tipo: Código del tipo de alerta (FK a TIPO_ALERTA).
            titulo: Título corto de la alerta.
            mensaje: Descripción detallada.
            codigo_prioridad: Prioridad explícita. Si None, usa el default del tipo.
            contexto: Datos estructurados adicionales (se almacena como JSONB).
            correo_id: FK a CORREO_ENTRANTE (opcional).
            adjunto_id: FK a ADJUNTOS_CORREO (opcional).
            factura_id: FK a FACTURA (opcional).
            correo_enviado: Si se envió email de notificación.

        Returns:
            ID de la alerta creada, o -1 si hubo error.
        """
        # Resolver prioridad
        if not codigo_prioridad:
            codigo_prioridad = CodigoTipoAlerta.PRIORIDAD_DEFAULT.get(
                codigo_tipo, CodigoPrioridad.media,
            )

        # Serializar contexto a JSON
        contexto_json = json.dumps(contexto, ensure_ascii=False, default=str) if contexto else None

        conn_propia = False
        try:
            if conn is None:
                conn = self._get_connection()
                conn_propia = True

            # LÓGICA DE RECUPERACIÓN AUTOMÁTICA DE FACTURA_ID
            # Si tenemos adjunto_id pero no factura_id, intentamos buscarlo
            if factura_id is None and adjunto_id is not None:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id_factura FROM facturacion.factura WHERE adjunto_id = %s LIMIT 1",
                            (adjunto_id,)
                        )
                        res = cur.fetchone()
                        if res:
                            factura_id = res[0]
                            logger.debug("Viculación automática: Alerta asociada a factura ID=%s por adjunto_id=%s", factura_id, adjunto_id)
                except Exception as e:
                    logger.debug("No se pudo vincular alerta a factura automáticamente: %s", e)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO FACTURACION.ALERTA (
                        CODIGO_TIPO_ALERTA, CODIGO_PRIORIDAD,
                        TITULO, MENSAJE, CONTEXTO,
                        CORREO_ID, ADJUNTO_ID, FACTURA_ID,
                        CORREO_ENVIADO
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
                    RETURNING ID_ALERTA
                    """,
                    (
                        codigo_tipo, codigo_prioridad,
                        titulo[:200], mensaje,
                        contexto_json,
                        correo_id, adjunto_id, factura_id,
                        correo_enviado,
                    ),
                )
                resultado = cur.fetchone()

            if conn_propia:
                conn.commit()

            id_alerta = resultado[0] if resultado else -1
            logger.debug(
                MensajesAlerta.alerta_creada,
                codigo_tipo, codigo_prioridad, titulo[:60],
            )
            return id_alerta

        except Exception as exc:
            logger.error(MensajesAlerta.alerta_persistencia_error, exc)
            if conn_propia and conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            return -1
        finally:
            if conn_propia and conn:
                try:
                    conn.close()
                except Exception:
                    pass
