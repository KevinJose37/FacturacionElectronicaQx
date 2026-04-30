"""Módulo que contiene funciones de validación para la factura electrónica y la validación
 de la misma por parte de la DIAN."""
 
# Third-party imports
from lxml import etree


def validar_documento_validacion_dian_v1(
    xml_invoice: etree._Element,
    xml_application_response: etree._Element
) -> bool:
    """Valida la existencia del documento de validación DIAN y su contenido.

    Args:
        xml_invoice: XML de la factura (Invoice).
        xml_application_response: XML de la respuesta DIAN (ApplicationResponse).

    Reglas:
    - Debe existir el Invoice
    - Debe existir el ApplicationResponse
    - Debe existir cbc:Description
    - El valor debe ser "Documento validado por la DIAN"

    Retorna:
        True si cumple con la validación, False en caso contrario.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

    resultado_validacion = False

    if xml_invoice is None:
        mensaje = 'No se encontró el XML de la factura electrónica (Invoice).'

    elif xml_application_response is None:
        mensaje = 'No se encontró el XML de validación DIAN (ApplicationResponse).'

    else:
        nodos_descripcion = xml_application_response.xpath(
            './cac:DocumentResponse/cac:Response/cbc:Description',
            namespaces=NAMESPACES
        )

        descripcion = (
            (nodos_descripcion[0].text or '').strip() if nodos_descripcion else None
        )

        if not descripcion:
            mensaje = 'No se encontró la descripción de validación DIAN.'

        elif 'Documento validado por la DIAN'.casefold() not in descripcion.casefold():
            mensaje = (
                f'Se encontró descripción "{descripcion}" '
                f'pero no corresponde a "Documento validado por la DIAN".'
            )

        else:
            mensaje = 'Documento validado correctamente por la DIAN.'
            resultado_validacion = True

    enviar_log_validacion(mensaje)

    return resultado_validacion
