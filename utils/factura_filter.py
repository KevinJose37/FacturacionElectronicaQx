"""Filtro de facturación-electrónica para determinar si un correo es válido.

El filtro aplica reglas de negocio para decidir si un correo debe procesarse
como factura electrónica colombiana. Si el correo no pasa el filtro, se marca
como no procesable y el flujo se detiene.

Criterios de filtrado:
    1. Asunto debe contener datos estructurados (NIT, número factura, etc.)
    2. Debe tener al menos un adjunto ZIP
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
        self.keywords = ["factura", "facturacion", "fe", "electronic bill"]

    def es_facturacion(self, parsed_subject: ParsedSubject) -> bool:
        """Determina si el correo es de facturación basándose en el asunto.

        Args:
            parsed_subject: Datos parseados del asunto.

        Returns:
            bool: True si se identifica como facturación.
        """
        # 1. Criterio de NIT (formato estándar)
        if parsed_subject.get("nit"):
            logger.debug("Identificado como facturación por NIT: %s", parsed_subject["nit"])
            return True

        # 2. Criterio de Palabras Clave
        asunto = parsed_subject.get("asunto_original", "").lower()
        for kw in self.keywords:
            # Usamos búsqueda de palabra completa para evitar falsos positivos con 'fe'
            if kw == "fe":
                if re.search(r"\bfe\b", asunto):
                    logger.debug("Identificado como facturación por palabra clave: %s", kw)
                    return True
            elif kw in asunto:
                logger.debug("Identificado como facturación por palabra clave: %s", kw)
                return True

        return False

    def evaluar(
        self,
        parsed_subject: ParsedSubject,
        tiene_zip: bool,
        remitente: Optional[str] = None,
    ) -> FilterResult:
        """Evalúa un correo contra las reglas de filtro.

        Args:
            parsed_subject: Datos parseados del asunto.
            tiene_zip: True si el correo contiene al menos un adjunto ZIP.
            remitente: Dirección de email del remitente (opcional).

        Returns:
            FilterResult con el resultado de la evaluación.
        """
        # Regla 1: Debe tener adjunto ZIP
        if not tiene_zip:
            return FilterResult(
                es_factura=False,
                motivo_rechazo="SIN_ADJUNTO_ZIP",
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
