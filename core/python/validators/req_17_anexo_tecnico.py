"""Módulo de validación del Anexo Técnico DIAN para facturas electrónicas."""

# Standard library imports
from typing import Tuple

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import validar_estructura_minima_ubl_v1
from core.python.utils.validacion import validar_xml_contra_xsd_v1


def validar_anexo_tecnico_v1(
    xml_factura: etree._Element, ruta_xsd: str,
) -> bool:
    """Valida el cumplimiento del Anexo Técnico DIAN (UBL 2.1 + reglas base).

    Verifica:
    - cumplimiento contra XSD (estructura UBL)
    - presencia de nodos mínimos obligatorios
    - base para validaciones adicionales tipo Schematron

    Args:
        xml_factura: Elemento raíz del XML de la factura.
        ruta_xsd: Ruta al archivo XSD de UBL Invoice.

    Returns:
        True si cumple el anexo técnico a nivel estructural, False en caso contrario.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    }

    resultado_validacion = False

    es_valido_xsd, msg_xsd = validar_xml_contra_xsd_v1(xml_factura, ruta_xsd)

    if not es_valido_xsd:
        mensaje = msg_xsd

    else:
        es_valido_estructura, msg_estructura = validar_estructura_minima_ubl_v1(
            xml_factura, NAMESPACES
        )

        if not es_valido_estructura:
            mensaje = msg_estructura

        else:
            resultado_validacion = True
            mensaje = (
                'El XML cumple con el Anexo Técnico a nivel estructural. '
                'Se validó contra el XSD de UBL 2.1 y se verificó la presencia '
                'de los nodos obligatorios.'
            )

    enviar_log_validacion(mensaje)

    return resultado_validacion
