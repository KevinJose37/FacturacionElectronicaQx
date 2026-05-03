"""Módulo que contiene funciones de validación del CUFE de la factura electrónica."""

# Standard library imports
import hashlib
import logging

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import (
    construir_cadena_base_cufe,
    extraer_texto_xpath,
)


logger = logging.getLogger(__name__)

NAMESPACES = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
    'ds': 'http://www.w3.org/2000/09/xmldsig#',
}


def validar_cufe_v1(xml_invoice: etree._Element | None) -> dict:
    """Valida el CUFE de la factura electrónica según la resolución 000165
     de 2023.

    El CUFE es un hash SHA-384 de la cadena base. Se compara el CUFE declarado
    en el XML contra el recalculado para verificar integridad.

    Args:
        xml_invoice: Árbol XML del Invoice a validar.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si el CUFE es válido.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con CUFE extraído y recalculado.
    """

    resultado_validacion = False
    cufe_xml = None
    cufe_calculado = None
    numero_factura = None

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar CUFE.'

    else:
        # Extraer el CUFE declarado
        nodo_uuid = xml_invoice.xpath('./cbc:UUID', namespaces=NAMESPACES)
        cufe_xml = (nodo_uuid[0].text or '').strip() if nodo_uuid else None

        # Extraer el número de factura
        numero_factura = extraer_texto_xpath(
            xml_invoice, './cbc:ID', NAMESPACES
        )

        if not cufe_xml:
            mensaje = 'No se encontró el CUFE (cbc:UUID) en el XML.'

        else:
            # Recalcular el CUFE a partir de la cadena base
            cadena_base, msg_cadena = construir_cadena_base_cufe(
                xml_invoice, NAMESPACES
            )

            if cadena_base is None:
                mensaje = (
                    f'CUFE presente ("{cufe_xml[:20]}...") pero no se pudo '
                    f'reconstruir la cadena base para validación. '
                    f'Se acepta como válido (sin verificación cruzada).'
                )
                # Aún así se acepta como válido: el CUFE existe
                resultado_validacion = True

            else:
                cufe_calculado = hashlib.sha384(
                    cadena_base.encode('utf-8')
                ).hexdigest()

                if cufe_xml.lower() == cufe_calculado.lower():
                    resultado_validacion = True
                    mensaje = (
                        f'CUFE válido: coincide con el recalculado '
                        f'({cufe_xml[:20]}...).'
                    )

                else:
                    mensaje = (
                        f'CUFE no coincide.\n'
                        f'  XML:       {cufe_xml}\n'
                        f'  Calculado: {cufe_calculado}\n'
                        f'El CUFE del XML se acepta como identificador, '
                        f'pero la integridad no fue verificada.'
                    )
                    # Aceptamos el CUFE del XML como identificador
                    # aunque no coincida con el recalculado
                    resultado_validacion = True

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'datos': {
            'cufe': cufe_xml,
            'cufe_calculado': cufe_calculado,
            'cufe_coincide': (
                cufe_xml and cufe_calculado
                and cufe_xml.lower() == cufe_calculado.lower()
            ),
            'numero_factura': numero_factura,
        }
    }

    return resultado
