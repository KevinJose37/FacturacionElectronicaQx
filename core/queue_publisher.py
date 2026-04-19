"""Publicador de eventos a cola para el módulo de ingesta de facturas.

Provee una interfaz común ``QueuePublisher`` con dos implementaciones:
- LocalQueuePublisher (JSONL)
- PostgresQueuePublisher (Base de Datos)
"""

from __future__ import annotations

import json
import logging
import uuid
import os
import psycopg
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class QueuePublisher(ABC):
    """Interfaz abstracta para publicadores de eventos de ingesta."""

    @abstractmethod
    def publish(self, event: dict[str, Any]) -> bool:
        """Publica un evento en la cola configurada.

        Args:
            event: Datos del evento a publicar.

        Returns:
            bool: True si tuvo éxito, False en caso contrario.
        """
        ...

    @staticmethod
    def _enriquecer_evento(event: dict[str, Any]) -> dict[str, Any]:
        """Agrega metadatos estándar al evento antes de publicarlo.

        Args:
            event: Evento original.

        Returns:
            dict: Evento con event_id, timestamp y source.
        """
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "source": "email_listener",
            **event,
        }


class LocalQueuePublisher(QueuePublisher):
    """Persiste eventos en un archivo JSONL local."""

    def __init__(self, local_path: str):
        """Inicializa el publicador local.

        Args:
            local_path: Ruta al archivo JSONL.
        """
        self.local_path = Path(local_path)
        self.local_path.parent.mkdir(parents=True, exist_ok=True)

    def publish(self, event: dict[str, Any]) -> bool:
        """Agrega una línea al archivo JSONL."""
        enriched = self._enriquecer_evento(event)
        try:
            with self.local_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(enriched, ensure_ascii=False) + "\n")
            return True
        except OSError as exc:
            logger.error(f"Error al escribir evento local: {exc}")
            return False


class PostgresQueuePublisher(QueuePublisher):
    """Inserta eventos en PostgreSQL."""

    def __init__(self, pg_config: dict[str, Any]):
        """Inicializa Postgres.

        Args:
            pg_config: Configuración de conexión.
        """
        self.config = pg_config

    def _get_connection(self) -> Any:
        """Establece conexión con la DB."""
        return psycopg.connect(
            host=self.config["host"],
            port=self.config["port"],
            dbname=self.config["dbname"],
            user=self.config["user"],
            password=os.environ["POSTGRES_PASSWORD"],
        )

    def publish(self, event: dict[str, Any]) -> bool:
        """Inserta el evento en FACTURACION.EVENTO_INGESTA."""
        enriched = self._enriquecer_evento(event)
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO FACTURACION.EVENTO_INGESTA 
                            (ID_EVENTO, FECHA_CREACION, ESTADO, ORIGEN, DATOS_JSON)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            enriched["event_id"],
                            enriched["timestamp"],
                            "PENDIENTE",
                            enriched["source"],
                            json.dumps(enriched, ensure_ascii=False),
                        ),
                    )
                conn.commit()
            return True
        except Exception as exc:
            logger.error(f"Error Postgres: {exc}")
            return False


def get_publisher(config: dict[str, Any]) -> QueuePublisher:
    """Fábrica de publicadores según configuración.

    Args:
        config: Diccionario de configuración central.

    Returns:
        QueuePublisher: Instancia configurada.
    """
    queue_cfg = config["queue"]
    backend = queue_cfg["backend"].strip().lower()

    if backend == "local":
        return LocalQueuePublisher(queue_cfg["local_path"])

    if backend == "postgres":
        return PostgresQueuePublisher({
            "host": os.environ["POSTGRES_HOST"],
            "port": int(os.environ["POSTGRES_PORT"]),
            "dbname": os.environ["POSTGRES_DB"],
            "user": os.environ["POSTGRES_USER"]
        })

    raise ValueError(f"Backend '{backend}' no soportado.")
