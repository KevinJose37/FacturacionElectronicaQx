"""Manejador de adjuntos ZIP de correos de facturación electrónica.

Descarga el primer adjunto .zip encontrado en un mensaje de correo y lo
guarda en la estructura de carpetas::

    downloads/{YYYY}/{MM}/{DD}/{nit_proveedor}/
    downloads/{YYYY}/{MM}/{DD}/sin_clasificar/   # Si el NIT no está disponible

Example:
    >>> from src.ingesta.attachment_handler import AttachmentHandler
    >>> handler = AttachmentHandler(config)
    >>> ruta = handler.descargar_zip(msg, parsed_subject)
"""

from __future__ import annotations

import email
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from email.message import Message

    from utils.email_parser import ParsedSubject

logger = logging.getLogger(__name__)


class AttachmentHandler:
    """Descargador de adjuntos ZIP desde objetos ``email.message.Message``.

    Attributes:
        base_path: Ruta raíz donde se almacenan los adjuntos descargados.
    """

    def __init__(self, config: dict) -> None:
        """Inicializa el manejador con la configuración de la aplicación.

        Args:
            config: Diccionario de configuración cargado desde settings.yaml.
                    Debe contener ``downloads.base_path``.
        """
        raw_base = config.get("downloads", {}).get("base_path", "downloads")
        self.base_path = Path(raw_base)
        logger.debug("AttachmentHandler inicializado. base_path=%s", self.base_path)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def descargar_zip(
        self,
        msg: "Message",
        parsed: "ParsedSubject",
    ) -> Path | None:
        """Descarga el primer adjunto .zip válido del correo.

        Args:
            msg: Objeto ``email.message.Message`` del correo.
            parsed: Resultado del parseo del asunto (``ParsedSubject``).

        Returns:
            Ruta absoluta al archivo descargado, o ``None`` si no se
            encontró ningún adjunto ZIP válido.
        """
        for part in msg.walk():
            filename = part.get_filename()
            if not filename or not filename.lower().endswith(".zip"):
                continue

            payload = part.get_payload(decode=True)
            if not payload:
                logger.warning(
                    "Adjunto %r está vacío (payload nulo); se omite.", filename
                )
                continue

            if len(payload) == 0:
                logger.warning(
                    "Adjunto %r tiene tamaño 0 bytes; se omite.", filename
                )
                continue

            destino = self._construir_ruta_destino(filename, parsed)
            destino.parent.mkdir(parents=True, exist_ok=True)

            destino.write_bytes(payload)
            logger.info(
                "Adjunto descargado: nombre_original=%r | tamaño=%d bytes | destino=%s",
                filename,
                len(payload),
                destino,
            )
            return destino

        logger.debug("No se encontró ningún adjunto ZIP en el correo.")
        return None

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def _construir_ruta_destino(
        self,
        filename: str,
        parsed: "ParsedSubject",
    ) -> Path:
        """Construye la ruta de destino para el adjunto.

        La estructura es:
        ``<base_path>/<YYYY>/<MM>/<DD>/<nit_o_sin_clasificar>/<filename>``

        Args:
            filename: Nombre original del archivo adjunto.
            parsed: Resultado del parseo del asunto.

        Returns:
            Ruta completa (``Path``) donde se guardará el adjunto.
        """
        ahora = datetime.now(tz=timezone.utc)
        anio = ahora.strftime("%Y")
        mes = ahora.strftime("%m")
        dia = ahora.strftime("%d")

        subcarpeta = parsed.get("nit") or "sin_clasificar"

        ruta = self.base_path / anio / mes / dia / subcarpeta / filename
        logger.debug("Ruta de destino calculada: %s", ruta)
        return ruta
