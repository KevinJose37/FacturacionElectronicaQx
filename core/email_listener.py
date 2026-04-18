"""Listener de correos IMAP para ingesta de facturas electrónicas.

Responsabilidades:
    - Conecta al servidor IMAP de Gmail con política de reintentos.
    - Obtiene correos NO leídos de la bandeja configurada.
    - Filtra únicamente los correos que posean adjuntos con extensión .zip.
    - Maneja correos reenviados (asunto con prefijo "Fwd:" o "RV:").
    - Marca cada correo como leído tras procesarlo exitosamente.
    - Publica un evento por cada correo procesado a la cola configurada.

Uso standalone::

    python -m src.ingesta.email_listener

Example:
    >>> from src.ingesta.email_listener import EmailListener
    >>> listener = EmailListener()
    >>> listener.run()
"""

from __future__ import annotations

import imaplib
import logging
import os
import time
from pathlib import Path
from typing import Generator

import yaml
from dotenv import load_dotenv

from core.queue_publisher import get_publisher
from utils.attachment_handler import AttachmentHandler
from utils.email_parser import EmailParser

# ---------------------------------------------------------------------------
# Configuración de entorno y ajustes
# ---------------------------------------------------------------------------
load_dotenv()

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "settings.yaml"


def _load_config() -> dict:
    """Carga el archivo settings.yaml.

    Returns:
        Diccionario con la configuración completa de la aplicación.

    Raises:
        FileNotFoundError: Si settings.yaml no existe en la ruta esperada.
    """
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {_CONFIG_PATH}")
    with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_CONFIG = _load_config()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log_level = getattr(logging, _CONFIG.get("logging", {}).get("level", "INFO"), logging.INFO)
_log_fmt = _CONFIG.get("logging", {}).get(
    "format", "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logging.basicConfig(level=_log_level, format=_log_fmt)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------


class EmailListener:
    """Listener IMAP para descarga y procesamiento de facturas electrónicas.

    Attributes:
        host: Dirección del servidor IMAP.
        port: Puerto SSL del servidor IMAP.
        usuario: Dirección de correo electrónico de la cuenta.
        carpeta: Carpeta IMAP a monitorear (por defecto INBOX).
        max_attempts: Número máximo de intentos de conexión.
        backoff_base: Base en segundos para el backoff exponencial.
    """

    def __init__(self) -> None:
        email_cfg = _CONFIG["email"]
        retry_cfg = _CONFIG.get("retry", {})

        self.host: str = email_cfg["host"]
        self.port: int = int(email_cfg.get("port", 993))
        self.usuario: str = email_cfg["usuario"]
        self.carpeta: str = email_cfg.get("carpeta", "INBOX")
        self.max_attempts: int = int(retry_cfg.get("max_attempts", 3))
        self.backoff_base: float = float(retry_cfg.get("backoff_base_seconds", 2))

        self._password: str = self._obtener_password()
        self._parser = EmailParser()
        self._attachment_handler = AttachmentHandler(_CONFIG)
        self._publisher = get_publisher(_CONFIG)

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _obtener_password() -> str:
        """Obtiene la contraseña de correo desde las variables de entorno.

        Returns:
            Contraseña de la cuenta de correo.

        Raises:
            EnvironmentError: Si EMAIL_PASSWORD no está definida.
        """
        password = os.getenv("EMAIL_PASSWORD", "")
        if not password:
            raise EnvironmentError(
                "La variable de entorno EMAIL_PASSWORD no está definida. "
                "Revisa el archivo .env."
            )
        return password

    def _conectar(self) -> imaplib.IMAP4_SSL:
        """Establece la conexión IMAP con política de reintentos exponenciales.

        Returns:
            Objeto IMAP4_SSL autenticado y con la carpeta seleccionada.

        Raises:
            ConnectionError: Si se agotan los intentos de conexión.
        """
        for intento in range(1, self.max_attempts + 1):
            try:
                logger.info(
                    "Conectando a %s:%s (intento %d/%d)…",
                    self.host,
                    self.port,
                    intento,
                    self.max_attempts,
                )
                conn = imaplib.IMAP4_SSL(self.host, self.port)
                conn.login(self.usuario, self._password)
                conn.select(self.carpeta)
                logger.info("Conexión IMAP establecida correctamente.")
                return conn
            except (imaplib.IMAP4.error, OSError) as exc:
                logger.warning("Intento %d fallido: %s", intento, exc)
                if intento < self.max_attempts:
                    espera = self.backoff_base**intento
                    logger.info("Reintentando en %.1f segundos…", espera)
                    time.sleep(espera)

        raise ConnectionError(
            f"No se pudo conectar a {self.host} tras {self.max_attempts} intentos."
        )

    # ------------------------------------------------------------------
    # Lógica de búsqueda y filtrado
    # ------------------------------------------------------------------

    def _obtener_uids_no_leidos(self, conn: imaplib.IMAP4_SSL) -> list[bytes]:
        """Busca los UIDs de correos no leídos en la carpeta configurada.

        Args:
            conn: Conexión IMAP autenticada.

        Returns:
            Lista de UIDs (bytes) de correos no leídos.
        """
        status, data = conn.uid("search", None, "UNSEEN")
        if status != "OK":
            logger.warning("La búsqueda IMAP retornó estado: %s", status)
            return []
        uids = data[0].split()
        logger.info("Correos no leídos encontrados: %d", len(uids))
        return uids

    def _fetch_message(
        self, conn: imaplib.IMAP4_SSL, uid: bytes
    ) -> bytes | None:
        """Descarga el contenido RFC-822 completo de un correo por UID.

        Args:
            conn: Conexión IMAP autenticada.
            uid: UID del correo a descargar.

        Returns:
            Contenido en bytes del correo, o None si la descarga falla.
        """
        status, data = conn.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not data or data[0] is None:
            logger.warning("No se pudo descargar el correo UID=%s", uid.decode())
            return None
        raw: bytes = data[0][1]
        return raw

    @staticmethod
    def _tiene_adjunto_zip(raw_message: bytes) -> bool:
        """Determina si el correo contiene al menos un adjunto .zip.

        Args:
            raw_message: Contenido RFC-822 del correo en bytes.

        Returns:
            True si existe al menos un adjunto con extensión .zip.
        """
        import email as _email

        msg = _email.message_from_bytes(raw_message)
        for part in msg.walk():
            filename = part.get_filename()
            if filename and filename.lower().endswith(".zip"):
                return True
        return False

    def _marcar_como_leido(self, conn: imaplib.IMAP4_SSL, uid: bytes) -> None:
        """Marca el correo indicado como leído (agrega flag \\Seen).

        Args:
            conn: Conexión IMAP autenticada.
            uid: UID del correo a marcar.
        """
        conn.uid("store", uid, "+FLAGS", "\\Seen")
        logger.debug("Correo UID=%s marcado como leído.", uid.decode())

    # ------------------------------------------------------------------
    # Procesamiento de un correo individual
    # ------------------------------------------------------------------

    def _procesar_correo(
        self, conn: imaplib.IMAP4_SSL, uid: bytes
    ) -> bool:
        """Procesa un único correo: parsea, descarga adjunto y publica evento.

        Args:
            conn: Conexión IMAP autenticada.
            uid: UID del correo a procesar.

        Returns:
            True si el correo fue procesado y publicado correctamente.
        """
        import email as _email

        uid_str = uid.decode()
        logger.info("── Procesando correo UID=%s", uid_str)

        raw = self._fetch_message(conn, uid)
        if raw is None:
            return False

        msg = _email.message_from_bytes(raw)
        asunto_raw: str = msg.get("Subject", "") or ""
        logger.debug("Asunto original: %r", asunto_raw)

        # Parsear asunto
        parsed = self._parser.parsear(asunto_raw)
        logger.debug("Asunto parseado: %s", parsed)

        # Descargar adjunto ZIP
        ruta_adjunto = self._attachment_handler.descargar_zip(msg, parsed)
        if ruta_adjunto is None:
            logger.warning(
                "Correo UID=%s no contiene adjunto ZIP válido; se omite.", uid_str
            )
            return False

        # Publicar evento
        evento = {
            "email_uid": uid_str,
            "parsed_subject": {
                "nit": parsed["nit"],
                "razon_social": parsed["razon_social"],
                "num_factura": parsed["num_factura"],
                "tipo": parsed["tipo"],
                "nombre_proveedor": parsed["nombre_proveedor"],
                "es_reenvio": parsed["es_reenvio"],
                "asunto_original": parsed["asunto_original"],
            },
            "attachment_path": str(ruta_adjunto),
            "raw_subject": asunto_raw,
        }

        publicado = self._publisher.publish(evento)
        if publicado:
            self._marcar_como_leido(conn, uid)
            logger.info("Correo UID=%s procesado y marcado como leído.", uid_str)
        else:
            logger.error("No se pudo publicar el evento para UID=%s.", uid_str)

        return publicado

    # ------------------------------------------------------------------
    # Punto de entrada principal
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Ejecuta el listener: conecta, procesa correos no leídos y cierra.

        Itera sobre todos los correos no leídos con adjunto ZIP y publica
        un evento por cada uno. Al finalizar cierra la conexión IMAP.
        """
        logger.info("═" * 60)
        logger.info("Iniciando EmailListener para cuenta: %s", self.usuario)
        logger.info("Carpeta IMAP: %s", self.carpeta)
        logger.info("═" * 60)

        conn = self._conectar()
        try:
            uids = self._obtener_uids_no_leidos(conn)
            if not uids:
                logger.info("No hay correos no leídos. Finalizando.")
                return

            procesados = 0
            omitidos = 0
            for uid in uids:
                raw = self._fetch_message(conn, uid)
                if raw is None:
                    omitidos += 1
                    continue

                if not self._tiene_adjunto_zip(raw):
                    logger.debug(
                        "Correo UID=%s sin adjunto ZIP — omitido.", uid.decode()
                    )
                    omitidos += 1
                    continue

                exito = self._procesar_correo(conn, uid)
                if exito:
                    procesados += 1
                else:
                    omitidos += 1

            logger.info(
                "Resumen: %d procesados, %d omitidos de %d total.",
                procesados,
                omitidos,
                len(uids),
            )
        finally:
            try:
                conn.close()
                conn.logout()
                logger.info("Conexión IMAP cerrada.")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Ejecución standalone
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    listener = EmailListener()
    listener.run()
