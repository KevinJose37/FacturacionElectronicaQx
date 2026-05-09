"""Manejador de adjuntos ZIP de correos de facturación electrónica.

Descarga adjuntos válidos (ZIP, XML, PDF) de un mensaje de correo y los
guarda en la estructura de carpetas::

    downloads/{YYYY}/{MM}/{DD}/{nit_proveedor}/
    downloads/{YYYY}/{MM}/{DD}/sin_clasificar/   # Si el NIT no está disponible

Example:
    >>> from src.ingesta.attachment_handler import AttachmentHandler
    >>> handler = AttachmentHandler(config)
    >>> adjuntos = handler.descargar_todos_adjuntos(msg, parsed_subject)
"""

from __future__ import annotations

import email
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from email.message import Message

    from utils.email_parser import ParsedSubject

logger = logging.getLogger(__name__)

# Extensiones válidas para adjuntos de facturación
_EXTENSIONES_FACTURA = {".zip", ".xml", ".pdf"}


@dataclass
class AdjuntoDescargado:
    """Representa un adjunto descargado del correo.

    Attributes:
        ruta: Ruta absoluta al archivo descargado.
        nombre_original: Nombre original del adjunto en el correo.
        extension: Extensión normalizada del archivo (.zip, .xml, .pdf).
    """
    ruta: Path
    nombre_original: str
    extension: str


class AttachmentHandler:
    """Descargador de adjuntos desde objetos ``email.message.Message``.

    Soporta la descarga de múltiples adjuntos ZIP, XML y PDF.

    Attributes:
        base_path: Ruta raíz donde se almacenan los adjuntos descargados.
    """

    def __init__(self, config: dict, temp_dir: str | Path | None = None) -> None:
        """Inicializa el manejador con la configuración de la aplicación.

        Args:
            config: Diccionario de configuración cargado desde settings.yaml.
                    Debe contener ``downloads.base_path``.
            temp_dir: Directorio temporal opcional para almacenar las descargas.
        """
        if temp_dir:
            self.base_path = Path(temp_dir)
            self._is_temp = True
        else:
            raw_base = config.get("downloads", {}).get("base_path", "downloads")
            self.base_path = Path(raw_base)
            self._is_temp = False
        logger.debug("AttachmentHandler inicializado. base_path=%s", self.base_path)

    def _tiene_adjunto_zip(self, raw_email: bytes) -> bool:
        """Verifica de forma rápida si el correo crudo contiene un adjunto ZIP.

        Args:
            raw_email: Contenido binario del correo.

        Returns:
            bool: True si se encuentra al menos un archivo .zip.
        """
        try:
            msg = email.message_from_bytes(raw_email)
            for part in msg.walk():
                filename = part.get_filename()
                if filename and filename.lower().endswith(".zip"):
                    return True
        except Exception as e:
            logger.error("Error al verificar adjuntos ZIP: %s", e)
        
        return False

    def tiene_adjuntos_factura(self, raw_email: bytes) -> bool:
        """Verifica si el correo contiene adjuntos válidos para facturación.

        Busca archivos .zip, .xml o .pdf adjuntos al correo.

        Args:
            raw_email: Contenido binario del correo.

        Returns:
            bool: True si se encuentra al menos un adjunto válido.
        """
        try:
            msg = email.message_from_bytes(raw_email)
            for part in msg.walk():
                filename = part.get_filename()
                if filename:
                    ext = Path(filename).suffix.lower()
                    if ext in _EXTENSIONES_FACTURA:
                        return True
        except Exception as e:
            logger.error("Error al verificar adjuntos de facturación: %s", e)
        
        return False

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

            destino = self.construir_ruta_destino(filename, parsed)
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

    def descargar_todos_adjuntos(
        self,
        msg: "Message",
        parsed: "ParsedSubject",
    ) -> List[AdjuntoDescargado]:
        """Descarga todos los adjuntos válidos (ZIP, XML, PDF) del correo.

        Itera sobre todas las partes del mensaje y descarga cualquier adjunto
        cuya extensión sea .zip, .xml o .pdf.

        Args:
            msg: Objeto ``email.message.Message`` del correo.
            parsed: Resultado del parseo del asunto (``ParsedSubject``).

        Returns:
            Lista de ``AdjuntoDescargado`` con los archivos descargados.
            Puede estar vacía si no se encontraron adjuntos válidos.
        """
        adjuntos: List[AdjuntoDescargado] = []

        for part in msg.walk():
            filename = part.get_filename()
            if not filename:
                continue

            ext = Path(filename).suffix.lower()
            if ext not in _EXTENSIONES_FACTURA:
                logger.debug("Adjunto ignorado (extensión no válida): %r", filename)
                continue

            payload = part.get_payload(decode=True)
            if not payload or len(payload) == 0:
                logger.warning("Adjunto %r está vacío; se omite.", filename)
                continue

            # Prefijo UUID solo para ZIPs (evita colisiones entre proveedores
            # que envían ZIPs con el mismo nombre en la misma fecha).
            # XML y PDF conservan su nombre original para emparejamiento.
            if ext == ".zip":
                prefijo = uuid.uuid4().hex[:8]
                nombre_guardado = f"{prefijo}_{filename}"
            else:
                nombre_guardado = filename

            destino = self.construir_ruta_destino(nombre_guardado, parsed)
            destino.parent.mkdir(parents=True, exist_ok=True)

            destino.write_bytes(payload)
            logger.info(
                "Adjunto descargado: nombre_original=%r | ext=%s | tamaño=%d bytes | destino=%s",
                filename, ext, len(payload), destino,
            )

            adjuntos.append(AdjuntoDescargado(
                ruta=destino,
                nombre_original=filename,
                extension=ext,
            ))

        if not adjuntos:
            logger.debug("No se encontraron adjuntos válidos en el correo.")

        return adjuntos

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    def construir_ruta_destino(
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
        if getattr(self, "_is_temp", False):
            ruta = self.base_path / filename
        else:
            ahora = datetime.now(tz=timezone.utc)
            anio = ahora.strftime("%Y")
            mes = ahora.strftime("%m")
            dia = ahora.strftime("%d")

            subcarpeta = parsed.get("nit") or "sin_clasificar"

            ruta = self.base_path / anio / mes / dia / subcarpeta / filename
        logger.debug("Ruta de destino calculada: %s", ruta)
        return ruta
