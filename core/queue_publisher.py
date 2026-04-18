"""Publicador de eventos a cola para el módulo de ingesta de facturas.

Provee una interfaz común ``QueuePublisher`` con dos implementaciones:

- ``LocalQueuePublisher``: Persiste eventos en un archivo JSON local
  (modo append, un evento por línea — JSONL).
- ``SQSQueuePublisher``: Publica eventos a una cola de AWS SQS via boto3.

La implementación activa se selecciona con ``queue.backend`` en settings.yaml.

Example:
    >>> from src.ingesta.queue_publisher import get_publisher
    >>> publisher = get_publisher(config)
    >>> publisher.publish({"email_uid": "123", ...})
    True
"""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Interfaz base
# ---------------------------------------------------------------------------


class QueuePublisher(ABC):
    """Interfaz abstracta para publicadores de eventos de ingesta.

    Toda implementación concreta debe implementar el método ``publish``.
    """

    @abstractmethod
    def publish(self, event: dict[str, Any]) -> bool:
        """Publica un evento en la cola configurada.

        El evento recibido se enriquece automáticamente con los campos
        ``event_id``, ``timestamp`` y ``source`` antes de publicarse.

        Args:
            event: Diccionario con los datos del evento. Se esperan al menos
                los campos definidos en ``email_listener.py``.

        Returns:
            ``True`` si el evento fue publicado correctamente, ``False`` en
            caso contrario.
        """
        ...

    # ------------------------------------------------------------------
    # Helpers compartidos
    # ------------------------------------------------------------------

    @staticmethod
    def _enriquecer_evento(event: dict[str, Any]) -> dict[str, Any]:
        """Agrega metadatos estándar al evento antes de publicarlo.

        Args:
            event: Evento original sin metadatos de sistema.

        Returns:
            Copia del evento enriquecido con ``event_id``, ``timestamp``
            y ``source``.
        """
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "source": "email_listener",
            **event,
        }


# ---------------------------------------------------------------------------
# Implementación LOCAL (JSONL)
# ---------------------------------------------------------------------------


class LocalQueuePublisher(QueuePublisher):
    """Publicador que persiste eventos en un archivo JSONL local.

    Cada llamada a ``publish`` agrega una línea JSON al final del archivo
    configurado. El directorio se crea si no existe.

    Attributes:
        local_path: Ruta al archivo JSONL de eventos.
    """

    def __init__(self, local_path: str) -> None:
        """Inicializa el publicador local.

        Args:
            local_path: Ruta relativa o absoluta al archivo de eventos JSONL.
        """
        self.local_path = Path(local_path)
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("LocalQueuePublisher configurado en: %s", self.local_path)

    def publish(self, event: dict[str, Any]) -> bool:
        """Persiste el evento en el archivo JSONL local.

        Args:
            event: Datos del evento a guardar.

        Returns:
            ``True`` si se guardó correctamente, ``False`` si hubo un error.
        """
        enriched = self._enriquecer_evento(event)
        try:
            with self.local_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(enriched, ensure_ascii=False) + "\n")
            logger.info(
                "Evento publicado localmente. event_id=%s | archivo=%s",
                enriched["event_id"],
                self.local_path,
            )
            return True
        except OSError as exc:
            logger.error("Error al escribir evento local: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Implementación SQS (AWS)
# ---------------------------------------------------------------------------


class SQSQueuePublisher(QueuePublisher):
    """Publicador que envía eventos a una cola de AWS SQS.

    Requiere que las variables de entorno ``AWS_ACCESS_KEY_ID``,
    ``AWS_SECRET_ACCESS_KEY`` y ``AWS_REGION`` estén definidas, o que el
    entorno de ejecución tenga permisos IAM suficientes.

    Attributes:
        queue_url: URL de la cola SQS de destino.
    """

    def __init__(self, queue_url: str) -> None:
        """Inicializa el publicador SQS.

        Args:
            queue_url: URL completa de la cola SQS.

        Raises:
            ImportError: Si boto3 no está instalado.
            ValueError: Si ``queue_url`` está vacía.
        """
        if not queue_url:
            raise ValueError(
                "queue.sqs_url no está configurada en settings.yaml. "
                "Defínela o cambia queue.backend a 'local'."
            )
        try:
            import boto3  # noqa: PLC0415

            self._sqs = boto3.client("sqs")
        except ImportError as exc:
            raise ImportError(
                "boto3 no está instalado. Ejecuta: pip install boto3"
            ) from exc

        self.queue_url = queue_url
        logger.info("SQSQueuePublisher configurado. queue_url=%s", self.queue_url)

    def publish(self, event: dict[str, Any]) -> bool:
        """Publica el evento en la cola SQS configurada.

        Args:
            event: Datos del evento a enviar.

        Returns:
            ``True`` si SQS confirmó la publicación, ``False`` en caso de error.
        """
        enriched = self._enriquecer_evento(event)
        body = json.dumps(enriched, ensure_ascii=False)
        try:
            response = self._sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=body,
                MessageGroupId="ingesta-facturas",          # solo para colas FIFO
                MessageDeduplicationId=enriched["event_id"],  # solo para colas FIFO
            )
            msg_id = response.get("MessageId", "?")
            logger.info(
                "Evento publicado en SQS. event_id=%s | MessageId=%s",
                enriched["event_id"],
                msg_id,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al publicar en SQS: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Implementación POSTGRES (Directa a tabla)
# ---------------------------------------------------------------------------


class PostgresQueuePublisher(QueuePublisher):
    """Publicador que inserta eventos en una tabla de PostgreSQL.

    Lee la contraseña desde la variable de entorno ``POSTGRES_PASSWORD``.
    La tabla destino es ``FACTURACION.EVENTO_INGESTA``.
    """

    def __init__(self, pg_config: dict[str, Any]) -> None:
        """Inicializa el publicador de Postgres.

        Args:
            pg_config: Diccionario con host, port, dbname, user.
        """
        self.config = pg_config
        self._check_driver()
        logger.info(
            "PostgresQueuePublisher configurado para %s@%s",
            self.config.get("user"),
            self.config.get("host"),
        )

    def _check_driver(self) -> None:
        try:
            import psycopg  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "psycopg no está instalado. Ejecuta: pip install psycopg[binary]"
            ) from exc

    def _get_connection(self) -> Any:
        import os  # noqa: PLC0415

        import psycopg  # noqa: PLC0415

        password = os.getenv("POSTGRES_PASSWORD", "")
        return psycopg.connect(
            host=self.config.get("host", "localhost"),
            port=self.config.get("port", 5432),
            dbname=self.config.get("dbname", "postgres"),
            user=self.config.get("user", "postgres"),
            password=password,
        )

    def publish(self, event: dict[str, Any]) -> bool:
        """Inserta el evento en la tabla FACTURACION.EVENTO_INGESTA.

        Args:
            event: Datos del evento a persistir.

        Returns:
            ``True`` si la inserción fue exitosa.
        """
        import json  # noqa: PLC0415

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

            logger.info("Evento persistido en Postgres. event_id=%s", enriched["event_id"])
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Error al publicar en Postgres: %s", exc)
            return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_publisher(config: dict[str, Any]) -> QueuePublisher:
    """Fábrica que retorna la implementación de cola correcta según settings.yaml.

    Lee ``queue.backend`` del diccionario de configuración y devuelve una
    instancia de ``LocalQueuePublisher`` o ``SQSQueuePublisher``.

    Args:
        config: Diccionario de configuración cargado desde settings.yaml.

    Returns:
        Instancia de ``QueuePublisher`` lista para usar.

    Raises:
        ValueError: Si ``queue.backend`` tiene un valor desconocido.

    Example:
        >>> publisher = get_publisher(config)
        >>> publisher.publish({"email_uid": "1"})
        True
    """
    queue_cfg = config.get("queue", {})
    backend = queue_cfg.get("backend", "local").strip().lower()

    if backend == "local":
        local_path = queue_cfg.get("local_path", "queue/events.json")
        return LocalQueuePublisher(local_path)

    if backend == "sqs":
        sqs_url = queue_cfg.get("sqs_url", "")
        return SQSQueuePublisher(sqs_url)

    if backend == "postgres":
        pg_cfg = queue_cfg.get("postgres", {})
        return PostgresQueuePublisher(pg_cfg)

    raise ValueError(
        f"queue.backend desconocido: '{backend}'. Valores válidos: 'local', 'sqs', 'postgres'."
    )

