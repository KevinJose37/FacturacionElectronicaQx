"""Filtro de facturación-electrónica para determinar si un correo es válido.

El filtro aplica reglas de negocio para decidir si un correo debe procesarse
como factura electrónica colombiana. Si el correo no pasa el filtro, se marca
como no procesable y el flujo se detiene.

Criterios de filtrado:
    1. Asunto debe contener datos estructurados (NIT, número factura, etc.)
       O palabras clave de facturación (factura, localizador, etc.)
    2. Debe tener al menos un adjunto válido (ZIP, XML, o PDF)
    3. Remitente debe ser un dominio válido (opcional, configurable)

Si el correo no cumple, se genera un evento de rechazo con el motivo.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from utils.email_parser import ParsedSubject

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Resultado de la evaluación de un correo.

    Attributes:
        es_factura: True si el correo es una factura válida.
        motivo_rechazo: Razón por la que se rechaza (None si es válido).
        parsed_subject: Datos extraídos del asunto (puede ser parcial).
    """

    es_factura: bool
    motivo_rechazo: Optional[str]
    parsed_subject: ParsedSubject

    def to_dict(self):
        return {
            "es_factura": self.es_factura,
            "motivo_rechazo": self.motivo_rechazo,
            "parsed_subject": self.parsed_subject,
        }


# Patrones de asuntos conocidos para facturación electrónica
_PATRON_LOCALIZADOR = re.compile(
    r"localizador\s+\d+\s*:\s*factura",
    re.IGNORECASE,
)

_PATRON_NIT_SEMICOLON = re.compile(
    r"\d{8,10}\s*;",  # NIT seguido de punto y coma
)

_PATRON_FACTURA_NUMERO = re.compile(
    r"factura\s*(electr[oó]nica)?\s*(no\.?|n[uú]mero|#)?\s*\w+",
    re.IGNORECASE,
)


class FacturaFilter:
    """Filtro que determina si un correo es una factura electrónica válida.

    Aplica múltiples reglas de validación y registra el motivo de rechazo
    cuando corresponda.
    """

    def __init__(self, config: dict):
        """Inicializa el filtro con configuración.

        Args:
            config: Dict con configuración. Puede incluir:
                - filter.require_nit: bool (default True)
                - filter.require_num_factura: bool (default True)
                - filter.allowed_senders: list[str] (default None = cualquier remitente)
        """
        filter_cfg = config.get("filter", {})
        self.require_nit = filter_cfg.get("require_nit", True)
        self.require_num_factura = filter_cfg.get("require_num_factura", True)
        self.allowed_senders = filter_cfg.get("allowed_senders", None)  # None = todos
        self.keywords = [
            "factura", "facturacion", "facturación",
            "electronic bill", "invoice",
        ]

    def es_facturacion(self, parsed_subject: ParsedSubject) -> bool:
        """Determina si el correo es de facturación basándose en el asunto.

        Aplica múltiples criterios de detección:
        1. Presencia de NIT en el asunto (formato estándar con ;)
        2. Palabras clave de facturación
        3. Patrón "Localizador XXXXX: Factura"
        4. Patrón de número de factura

        Args:
            parsed_subject: Datos parseados del asunto.

        Returns:
            bool: True si se identifica como facturación.
        """
        asunto = parsed_subject.get("asunto_original", "")

        # 1. Criterio de NIT (formato estándar)
        if parsed_subject.get("nit"):
            logger.debug("Identificado como facturación por NIT: %s", parsed_subject["nit"])
            return True

        asunto_lower = asunto.lower()

        # 2. Criterio de Palabras Clave
        for kw in self.keywords:
            if kw in asunto_lower:
                logger.debug("Identificado como facturación por palabra clave: %s", kw)
                return True

        # 3. Patrón "Localizador 130123998: Factura"
        if _PATRON_LOCALIZADOR.search(asunto):
            logger.debug("Identificado como facturación por patrón 'Localizador: Factura'")
            return True

        # 4. Patrón NIT;... (formato semicolon sin parseo completo)
        if _PATRON_NIT_SEMICOLON.search(asunto):
            logger.debug("Identificado como facturación por patrón NIT;")
            return True

        # 5. Patrón "Factura electrónica No. XXX" o similar
        if _PATRON_FACTURA_NUMERO.search(asunto):
            logger.debug("Identificado como facturación por patrón de número de factura")
            return True

        # 6. Criterio FE como palabra aislada
        if re.search(r"\bfe\b", asunto_lower):
            logger.debug("Identificado como facturación por palabra clave: fe")
            return True

        return False

    def evaluar(
        self,
        parsed_subject: ParsedSubject,
        tiene_adjuntos_factura: bool,
        remitente: Optional[str] = None,
    ) -> FilterResult:
        """Evalúa un correo contra las reglas de filtro.

        Args:
            parsed_subject: Datos parseados del asunto.
            tiene_adjuntos_factura: True si el correo contiene al menos un
                adjunto válido (ZIP, XML o PDF).
            remitente: Dirección de email del remitente (opcional).

        Returns:
            FilterResult con el resultado de la evaluación.
        """
        # Regla 1: Debe tener al menos un adjunto válido (ZIP, XML o PDF)
        if not tiene_adjuntos_factura:
            return FilterResult(
                es_factura=False,
                motivo_rechazo="SIN_ADJUNTOS_FACTURA",
                parsed_subject=parsed_subject,
            )

        # Regla 2: Si se requiere NIT, debe estar presente y válido
        if self.require_nit and not parsed_subject.get("nit"):
            return FilterResult(
                es_factura=False,
                motivo_rechazo="NIT_NO_ENCONTRADO",
                parsed_subject=parsed_subject,
            )

        # Regla 3: Si se requiere número de factura, debe estar presente
        if self.require_num_factura and not parsed_subject.get("num_factura"):
            return FilterResult(
                es_factura=False,
                motivo_rechazo="NUM_FACTURA_NO_ENCONTRADO",
                parsed_subject=parsed_subject,
            )

        # Regla 4: Remitente en lista blanca (si está configurada)
        if self.allowed_senders is not None:
            if remitente is None:
                return FilterResult(
                    es_factura=False,
                    motivo_rechazo="REMITENTE_DESCONOCIDO",
                    parsed_subject=parsed_subject,
                )
            if remitente not in self.allowed_senders:
                return FilterResult(
                    es_factura=False,
                    motivo_rechazo="REMITENTE_NO_AUTORIZADO",
                    parsed_subject=parsed_subject,
                )

        # Pasó todas las reglas
        logger.info(
            "Correo aprobado como factura: nit=%s num_factura=%s",
            parsed_subject.get("nit"),
            parsed_subject.get("num_factura"),
        )
        return FilterResult(
            es_factura=True,
            motivo_rechazo=None,
            parsed_subject=parsed_subject,
        )
