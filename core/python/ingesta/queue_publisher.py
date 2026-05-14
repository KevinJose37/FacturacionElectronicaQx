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

logger = logging.getLogger(__name__)


class QueuePublisher(ABC):
    """Interfaz abstracta para publicadores de eventos de ingesta."""

    @abstractmethod
    def publish(self, event: dict, db_conn=None) -> bool:
        """Publica un evento en la cola configurada.

        Args:
            event: Datos del evento a publicar.

        Returns:
            bool: True si tuvo éxito, False en caso contrario.
        """
        ...

    @staticmethod
    def _enriquecer_evento(event: dict) -> dict:
        """Agrega metadatos estándar al evento antes de publicarlo.

        Args:
            event: Evento original.

        Returns:
            dict: Evento con event_id, timestamp y source.
        """
        resultado = {
            'event_id': str(uuid.uuid4()),
            'timestamp': datetime.now(tz=timezone.utc).isoformat(),
            'source': 'email_listener',
            **event,
        }
        return resultado


class LocalQueuePublisher(QueuePublisher):
    """Persiste eventos en un archivo JSONL local."""

    def __init__(self, local_path: str):
        """Inicializa el publicador local.

        Args:
            local_path: Ruta al archivo JSONL.
        """
        self.local_path = Path(local_path)
        self.local_path.parent.mkdir(parents=True, exist_ok=True)

    def publish(self, event: dict, db_conn=None) -> bool:
        """Agrega una línea al archivo JSONL."""
        enriched = self._enriquecer_evento(event)
        try:
            with self.local_path.open('a', encoding='utf-8') as fh:
                fh.write(json.dumps(enriched, ensure_ascii=False) + '\n')
            return True
        except OSError as exc:
            logger.error('Error al escribir evento local: %s', exc)
            return False


class PostgresQueuePublisher(QueuePublisher):
    """Inserta eventos en PostgreSQL."""

    def __init__(self, pg_config: dict):
        """Inicializa Postgres.

        Args:
            pg_config: Configuración de conexión.
        """
        self.config = pg_config

    def _get_connection(self):
        """Establece conexión con la DB."""
        conexion = psycopg.connect(
            host=self.config['host'],
            port=self.config['port'],
            dbname=self.config['dbname'],
            user=self.config['user'],
            password=os.environ['POSTGRES_PASSWORD'],
        )
        return conexion

    def publish(self, event: dict, db_conn=None) -> bool:
        """Publica el evento (la inserción en EVENTO_INGESTA se hace en el repository)."""
        enriched = self._enriquecer_evento(event)
        try:
            logger.info(
                'Evento publicado: type=%s adjunto_id=%s',
                enriched.get('event_type'),
                enriched.get('id_adjunto_zip') or enriched.get('id_adjunto_xml'),
            )
            if db_conn:
                with db_conn.cursor() as cur:
                    cur.execute("NOTIFY factura_nueva")
            return True
        except Exception as exc:
            logger.error('Error Postgres: %s', exc)
            return False


def get_publisher(config: dict) -> QueuePublisher:
    """Fábrica de publicadores según configuración.

    Args:
        config: Diccionario de configuración central.

    Returns:
        QueuePublisher: Instancia configurada.
    """
    queue_cfg = config['queue']
    backend = queue_cfg['backend'].strip().lower()

    if backend == 'local':
        publisher = LocalQueuePublisher(queue_cfg['local_path'])
    elif backend == 'postgres':
        publisher = PostgresQueuePublisher({
            'host': os.environ['POSTGRES_HOST'],
            'port': int(os.environ['POSTGRES_PORT']),
            'dbname': os.environ['POSTGRES_DB'],
            'user': os.environ['POSTGRES_USER'],
        })
    else:
        raise ValueError(f"Backend '{backend}' no soportado.")

    return publisher
