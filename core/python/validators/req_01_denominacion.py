"""Módulo que contiene las versiones de la validación de la denominación del documento de
 la factura electrónica."""

# Third-party imports
from lxml import etree


def validar_denominacion_v1(xml_factura: etree._Element) -> bool:
    """Valida que la factura electrónica esté denominada expresamente como 'Factura
     Electrónica de Venta' como exige la resolución 000165 de 2025.
     
    Args:
        xml_factura: Árbol XML de la factura electrónica a validar.
    
    Returns:
        True si la denominación es correcta, False en caso contrario.
    
    """
    DENOMINACION_REQUERIDA = 'Factura Electrónica de Venta'
    XPATH = './cbc:ProfileID'
    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    resultado_validacion = False

    nodos = xml_factura.xpath(XPATH, namespaces=NAMESPACES)

    if nodos:
        denominacion = (nodos[0].text or '').strip()

        if DENOMINACION_REQUERIDA.casefold() in denominacion.casefold():
            enviar_log_validacion('Denominación correcta.')
            resultado_validacion = True
        else:
            enviar_log_validacion(
                f'Denominación incorrecta: "{denominacion}". '
                f'Debe contener "{DENOMINACION_REQUERIDA}".'
            )
    else:
        enviar_log_validacion(
            'No se encontró el nodo cbc:ProfileID para validar la denominación.'
        )

    return resultado_validacion
