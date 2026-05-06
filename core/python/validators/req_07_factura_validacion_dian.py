"""Módulo que contiene funciones de validación para la factura electrónica y la validación
 de la misma por parte de la DIAN."""
 
# Standard library imports
import logging

# Third-party imports
from lxml import etree
from metadata.db_metadata import IdTipoError, IdTipoEventoDian


logger = logging.getLogger(__name__)


def validar_documento_validacion_dian_v1(
    xml_invoice: etree._Element,
    xml_application_response: etree._Element
) -> dict:
    """Valida la existencia del documento de validación DIAN y su contenido.

    Args:
        xml_invoice: XML de la factura (Invoice).
        xml_application_response: XML de la respuesta DIAN (ApplicationResponse).

    Returns:
        Diccionario con:
        - 'valido': bool indicando si el documento fue validado por la DIAN.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con código y descripción de la respuesta DIAN, y líneas de detalle.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

    resultado_validacion = False
    codigo_respuesta = None
    descripcion_respuesta = None
    id_rastreo = None
    cufe_validado = None
    lineas_respuesta = []

    if xml_invoice is None:
        mensaje = 'No se encontró el XML de la factura electrónica (Invoice).'

    elif xml_application_response is None:
        mensaje = 'No se encontró el XML de validación DIAN (ApplicationResponse).'

    else:
        # Extraer ID del documento de validación (número de rastreo)
        nodo_id = xml_application_response.xpath(
            './cbc:ID', namespaces=NAMESPACES
        )
        id_rastreo = (nodo_id[0].text or '').strip() if nodo_id else None

        # Extraer respuesta principal
        nodos_codigo = xml_application_response.xpath(
            './cac:DocumentResponse/cac:Response/cbc:ResponseCode',
            namespaces=NAMESPACES
        )
        nodos_descripcion = xml_application_response.xpath(
            './cac:DocumentResponse/cac:Response/cbc:Description',
            namespaces=NAMESPACES
        )

        codigo_respuesta = (
            (nodos_codigo[0].text or '').strip() if nodos_codigo else None
        )
        descripcion_respuesta = (
            (nodos_descripcion[0].text or '').strip() if nodos_descripcion else None
        )

        # Extraer CUFE validado
        nodo_cufe = xml_application_response.xpath(
            './cac:DocumentResponse/cac:DocumentReference/cbc:UUID',
            namespaces=NAMESPACES
        )
        cufe_validado = (nodo_cufe[0].text or '').strip() if nodo_cufe else None

        # Extraer líneas de respuesta (detalles de validación)
        nodos_linea = xml_application_response.xpath(
            './cac:DocumentResponse/cac:LineResponse', namespaces=NAMESPACES
        )
        for linea in nodos_linea:
            nodo_line_id = linea.xpath(
                './cac:LineReference/cbc:LineID', namespaces=NAMESPACES
            )
            nodo_resp_code = linea.xpath(
                './cac:Response/cbc:ResponseCode', namespaces=NAMESPACES
            )
            nodo_resp_desc = linea.xpath(
                './cac:Response/cbc:Description', namespaces=NAMESPACES
            )
            lineas_respuesta.append({
                'linea_id': (nodo_line_id[0].text or '').strip() if nodo_line_id else None,
                'codigo': (nodo_resp_code[0].text or '').strip() if nodo_resp_code else None,
                'descripcion': (nodo_resp_desc[0].text or '').strip() if nodo_resp_desc else None,
            })

        if not codigo_respuesta:
            mensaje = 'No se encontró el código de validación DIAN.'

        elif codigo_respuesta != IdTipoEventoDian.documento_validado_dian:
            mensaje = (
                f'Se encontró código "{codigo_respuesta}" ({descripcion_respuesta}) '
                f'pero no corresponde a "Documento validado por la DIAN" ({IdTipoEventoDian.documento_validado_dian}).'
            )

        else:
            mensaje = 'Documento validado correctamente por la DIAN.'
            resultado_validacion = True

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'id_error': IdTipoError.validacion_dian_fallo if not resultado_validacion else None,
        'datos': {
            'id_rastreo': id_rastreo,
            'codigo_evento': codigo_respuesta,
            'codigo_respuesta': codigo_respuesta,
            'descripcion_respuesta': descripcion_respuesta,
            'cufe_validado': cufe_validado,
            'lineas_respuesta': lineas_respuesta,
        }
    }

    return resultado
