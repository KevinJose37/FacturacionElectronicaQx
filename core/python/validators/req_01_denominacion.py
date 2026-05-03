"""Módulo que contiene las versiones de la validación de la denominación del documento de
 la factura electrónica."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree


logger = logging.getLogger(__name__)


def validar_denominacion_v1(xml_factura: etree._Element) -> dict:
    """Valida que la factura electrónica esté denominada expresamente como 'Factura
     Electrónica de Venta' como exige la resolución 000165 de 2025.
     
    Args:
        xml_factura: Árbol XML de la factura electrónica a validar.
    
    Returns:
        Diccionario con:
        - 'valido': bool indicando si la denominación es correcta.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con la denominación encontrada.
    
    """
    DENOMINACION_REQUERIDA = 'Factura Electrónica de Venta'
    XPATH = './cbc:ProfileID'
    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    resultado_validacion = False
    denominacion = None

    nodos = xml_factura.xpath(XPATH, namespaces=NAMESPACES)

    if nodos:
        denominacion = (nodos[0].text or '').strip()

        if DENOMINACION_REQUERIDA.casefold() in denominacion.casefold():
            mensaje = 'Denominación correcta.'
            resultado_validacion = True
        else:
            mensaje = (
                f'Denominación incorrecta: "{denominacion}". '
                f'Debe contener "{DENOMINACION_REQUERIDA}".'
            )
    else:
        mensaje = 'No se encontró el nodo cbc:ProfileID para validar la denominación.'

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'datos': {
            'denominacion': denominacion,
        }
    }

    return resultado
