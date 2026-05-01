"""Parser de asuntos de correo para facturación electrónica colombiana.

El formato estándar del asunto es::

    {NIT};{RAZON_SOCIAL};{NUM_FACTURA};{TIPO};{NOMBRE_PROVEEDOR}

Ejemplo real::

    811028188;INSTITUCION UNIVERSITARIA SALAZAR Y HERRERA;FEA46067;01;INSTITUCIÓN UNIVERSITARIA SALAZAR Y HERRERA

El parser es tolerante a fallos: si el asunto no sigue el formato, extrae
lo que puede y deja los campos faltantes como ``None``.

Example:
    >>> from src.ingesta.email_parser import EmailParser
    >>> parser = EmailParser()
    >>> result = parser.parsear("811028188;EMPRESA XYZ;FEA001;01;EMPRESA XYZ")
    >>> result["nit"]
    '811028188'
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from email.message import Message

logger = logging.getLogger(__name__)

# Prefijos de reenvío típicos (case-insensitive)
_FORWARD_PREFIXES: tuple[str, ...] = ("fwd:", "fw:", "rv:", "reen:")

# Expresión regular para validar un NIT colombiano (8 o 9 dígitos)
_NIT_RE = re.compile(r"^\d{8,10}$")


class ParsedSubject(TypedDict):
    """Resultado del parseo del asunto de un correo de factura.

    Attributes:
        nit: NIT del proveedor (puede ser None si no se detectó).
        razon_social: Razón social del proveedor.
        num_factura: Número de factura electrónica.
        tipo: Tipo de documento (e.g. "01").
        nombre_proveedor: Nombre comercial del proveedor.
        es_reenvio: Indica si el correo fue reenviado.
        asunto_original: Asunto completo sin modificaciones.
    """

    nit: str | None
    razon_social: str | None
    num_factura: str | None
    tipo: str | None
    nombre_proveedor: str | None
    es_reenvio: bool
    asunto_original: str


class EmailParser:
    """Parser tolerante de asuntos de correos de factura electrónica.

    Intenta extraer los campos del formato estándar separado por punto y
    coma. Si el asunto no sigue el formato, retorna los campos parciales
    disponibles con los faltantes en ``None``.
    """

    def parsear(self, asunto: str) -> ParsedSubject:
        """Parsea el asunto de un correo de factura electrónica.

        Args:
            asunto: Texto del asunto del correo, tal como llega del servidor.

        Returns:
            ``ParsedSubject`` con los campos extraídos. Los campos que no
            pudieron determinarse se establecen en ``None``.

        Example:
            >>> parser = EmailParser()
            >>> r = parser.parsear("Fwd: 123456789;MI EMPRESA;FAC-001;01;MI EMPRESA")
            >>> r["es_reenvio"]
            True
            >>> r["nit"]
            '123456789'
        """
        asunto_original = asunto
        asunto_limpio, es_reenvio = self._strip_forward_prefix(asunto)

        if not asunto_limpio:
            logger.warning("El asunto está vacío; retornando campos en None.")
            return self._vacio(asunto_original, es_reenvio)

        partes = [p.strip() for p in asunto_limpio.split(";")]

        if len(partes) < 2:
            # El asunto no sigue el formato en absoluto
            logger.warning(
                "Asunto sin formato estándar: %r — extracción parcial.", asunto_original
            )
            return self._parcial(partes, asunto_original, es_reenvio)

        nit = self._extraer_nit(partes[0])
        razon_social = partes[1] if len(partes) > 1 else None
        num_factura = partes[2] if len(partes) > 2 else None
        tipo = partes[3] if len(partes) > 3 else None
        nombre_proveedor = partes[4] if len(partes) > 4 else None

        if nit is None:
            logger.debug(
                "El primer campo %r no es un NIT válido; se guarda como None.", partes[0]
            )

        result: ParsedSubject = {
            "nit": nit,
            "razon_social": razon_social or None,
            "num_factura": num_factura or None,
            "tipo": tipo or None,
            "nombre_proveedor": nombre_proveedor or None,
            "es_reenvio": es_reenvio,
            "asunto_original": asunto_original,
        }
        logger.debug("Parseo exitoso: %s", result)
        return result

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_forward_prefix(asunto: str) -> tuple[str, bool]:
        """Elimina el prefijo de reenvío del asunto si está presente.

        Args:
            asunto: Texto del asunto original.

        Returns:
            Tupla ``(asunto_sin_prefijo, es_reenvio)``. ``es_reenvio`` es
            ``True`` si se detectó y eliminó un prefijo de reenvío.
        """
        texto = asunto.strip()
        texto_lower = texto.lower()
        for prefijo in _FORWARD_PREFIXES:
            if texto_lower.startswith(prefijo):
                return texto[len(prefijo):].strip(), True
        return texto, False

    @staticmethod
    def _extraer_nit(valor: str) -> str | None:
        """Valida y retorna el NIT si tiene el formato esperado.

        Args:
            valor: Primer campo obtenido del split por punto y coma.

        Returns:
            El NIT como cadena de texto, o ``None`` si el valor no es válido.
        """
        limpio = valor.strip().replace("-", "")
        return limpio if _NIT_RE.match(limpio) else None

    @staticmethod
    def _vacio(asunto_original: str, es_reenvio: bool) -> ParsedSubject:
        """Retorna un ``ParsedSubject`` completamente nulo.

        Args:
            asunto_original: Asunto sin procesar.
            es_reenvio: Indica si el correo fue reenviado.

        Returns:
            ``ParsedSubject`` con todos los campos de datos en ``None``.
        """
        return ParsedSubject(
            nit=None,
            razon_social=None,
            num_factura=None,
            tipo=None,
            nombre_proveedor=None,
            es_reenvio=es_reenvio,
            asunto_original=asunto_original,
        )

    @staticmethod
    def _parcial(partes: list[str], asunto_original: str, es_reenvio: bool) -> ParsedSubject:
        """Construye un ``ParsedSubject`` con extracción parcial.

        Cuando el asunto tiene menos de dos campos separados por punto y
        coma, se guarda lo disponible y el resto queda en ``None``.

        Args:
            partes: Lista de fragmentos obtenidos del split.
            asunto_original: Asunto sin procesar.
            es_reenvio: Indica si el correo fue reenviado.

        Returns:
            ``ParsedSubject`` con campos parciales.
        """
        return ParsedSubject(
            nit=None,
            razon_social=partes[0] if partes else None,
            num_factura=None,
            tipo=None,
            nombre_proveedor=None,
            es_reenvio=es_reenvio,
            asunto_original=asunto_original,
        )

    def extraer_cuerpos_mensaje(self, msg: "Message") -> tuple[str | None, str | None]:
        """Extrae el cuerpo de texto y HTML del mensaje.

        Returns:
            Tupla (cuerpo_texto, cuerpo_html).
        """
        cuerpo_texto = None
        cuerpo_html = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition"))

                if "attachment" in disposition:
                    continue

                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                if content_type == "text/plain" and not cuerpo_texto:
                    cuerpo_texto = payload.decode(errors="ignore")
                elif content_type == "text/html" and not cuerpo_html:
                    cuerpo_html = payload.decode(errors="ignore")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                if msg.get_content_type() == "text/plain":
                    cuerpo_texto = payload.decode(errors="ignore")
                else:
                    cuerpo_html = payload.decode(errors="ignore")

        return cuerpo_texto, cuerpo_html
