"""Listener de correos IMAP para ingesta de facturas electrónicas."""

from __future__ import annotations

import imaplib
import logging
import os
import time
import email as _email
from pathlib import Path

import yaml
from dotenv import load_dotenv

from core.python.ingesta.queue_publisher import get_publisher
from utils.attachment_handler import AttachmentHandler
from utils.email_parser import EmailParser

load_dotenv()

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "settings.yaml"

def _load_config() -> dict:
    """Carga la configuración desde el archivo YAML."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuración no encontrada en {_CONFIG_PATH}")
    with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)

_CONFIG = _load_config()
logger = logging.getLogger(__name__)


class EmailListener:
    """Listener IMAP para procesamiento de facturas."""

    def __init__(self):
        """Inicializa el listener con configuración y dependencias."""
        email_cfg = _CONFIG["email"]
        retry_cfg = _CONFIG.get("retry", {})

        self.host = email_cfg["host"]
        self.port = int(email_cfg["port"])
        self.usuario = os.environ["EMAIL_USER"]
        self.carpeta = email_cfg["carpeta"]
        self.max_attempts = int(retry_cfg["max_attempts"])
        self.backoff_base = float(retry_cfg["backoff_base_seconds"])

        self._password = os.environ["EMAIL_PASSWORD"]
        self._parser = EmailParser()
        self._attachment_handler = AttachmentHandler(_CONFIG)
        self._publisher = get_publisher(_CONFIG)

    def _conectar(self) -> imaplib.IMAP4_SSL:
        """Establece conexión IMAP con reintentos."""
        for intento in range(1, self.max_attempts + 1):
            try:
                conn = imaplib.IMAP4_SSL(self.host, self.port)
                conn.login(self.usuario, self._password)
                conn.select(self.carpeta)
                return conn
            except (imaplib.IMAP4.error, OSError) as exc:
                if intento == self.max_attempts:
                    raise ConnectionError(f"Falla conexión IMAP: {exc}")
                time.sleep(self.backoff_base**intento)

    def _obtener_uids(self, conn: imaplib.IMAP4_SSL) -> list[bytes]:
        """Obtiene UIDs de correos no leídos."""
        status, data = conn.uid("search", None, "UNSEEN")
        return data[0].split() if status == "OK" else []

    @staticmethod
    def _tiene_adjunto_zip(msg: _email.message.Message) -> str | None:
        """Verifica si el mensaje tiene adjuntos ZIP y retorna su nombre."""
        for part in msg.walk():
            filename = part.get_filename()
            if filename and filename.lower().endswith(".zip"):
                return filename
        return None

    def _procesar_correo(self, conn: imaplib.IMAP4_SSL, uid: bytes) -> bool:
        """Procesa un correo individual.

        Args:
            conn: Conexión IMAP.
            uid: UID del correo.

        Returns:
            bool: True si procesó correctamente.
        """
        status, data = conn.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not data:
            return False

        raw = data[0][1]
        msg = _email.message_from_bytes(raw)
        nombre_zip = self._tiene_adjunto_zip(msg)

        if not nombre_zip:
            return False

        parsed = self._parser.parsear(msg.get("Subject", ""))
        ruta = self._attachment_handler.descargar_zip(msg, parsed)

        if not ruta:
            return False

        exito = self._publisher.publish({
            "email_uid": uid.decode(),
            "parsed_subject": parsed,
            "attachment_path": str(ruta)
        })

        if exito:
            conn.uid("store", uid, "+FLAGS", "\\Seen")
        return exito

    def run(self):
        """Ejecuta el ciclo de ingesta."""
        try:
            with self._conectar() as conn:
                uids = self._obtener_uids(conn)
                procesados = sum(1 for uid in uids if self._procesar_correo(conn, uid))
                logger.info(f"Finalizado: {procesados}/{len(uids)} procesados.")
        except Exception as e:
            logger.error(f"Error en ejecución: {e}")


if __name__ == "__main__":
    EmailListener().run()