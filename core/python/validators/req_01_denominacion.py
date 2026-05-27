"""Módulo que contiene las versiones de la validación de la denominación del documento de
 la factura electrónica."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree
from metadata.db_metadata import IdTipoError, IdTipoDocumentoDian


logger = logging.getLogger(__name__)


def validar_denominacion_v1(xml_factura: etree._Element) -> dict:
    """Valida que la factura electrónica esté denominada expresamente como 'Factura
     Electrónica de Venta' como exige la resolución 000165 de 2025.

    Extrae además el código de tipo de documento (InvoiceTypeCode) y lo valida
    contra el catálogo TIPO_DOCUMENTO_DIAN.
     
    Args:
        xml_factura: Árbol XML de la factura electrónica a validar.
    
    Returns:
        Diccionario con:
        - 'valido': bool indicando si la denominación es correcta.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con la denominación y el código de tipo de documento encontrados.
    
    """
    DENOMINACION_REQUERIDA = 'Factura Electrónica de Venta'
    XPATH_PROFILE = './cbc:ProfileID'
    XPATH_TYPE_CODE = './cbc:InvoiceTypeCode'
    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    resultado_validacion = False
    denominacion = None
    codigo_tipo_documento = None
    id_error = None

    nodos_profile = xml_factura.xpath(XPATH_PROFILE, namespaces=NAMESPACES)
    nodos_type_code = xml_factura.xpath(XPATH_TYPE_CODE, namespaces=NAMESPACES)

    # Extraer código de tipo de documento (InvoiceTypeCode)
    if nodos_type_code:
        codigo_tipo_documento = (nodos_type_code[0].text or '').strip() or None

    if nodos_profile:
        denominacion = (nodos_profile[0].text or '').strip()

        if DENOMINACION_REQUERIDA.casefold() not in denominacion.casefold():
            mensaje = (
                f'Denominación incorrecta: "{denominacion}". '
                f'Debe contener "{DENOMINACION_REQUERIDA}".'
            )
            id_error = IdTipoError.denominacion_incorrecta

        elif not codigo_tipo_documento:
            mensaje = (
                'Denominación correcta, pero no se encontró el código de tipo '
                'de documento (InvoiceTypeCode).'
            )
            # Se permite continuar: la denominación es válida
            resultado_validacion = True

        elif not IdTipoDocumentoDian.es_factura_valida(codigo_tipo_documento):
            mensaje = (
                f'Denominación correcta, pero el código de tipo de documento '
                f'"{codigo_tipo_documento}" no corresponde a una factura '
                f'electrónica válida.'
            )
            id_error = IdTipoError.tipo_documento_dian_invalido

        else:
            mensaje = 'Denominación correcta.'
            resultado_validacion = True
    else:
        mensaje = 'No se encontró el nodo cbc:ProfileID para validar la denominación.'
        id_error = IdTipoError.profile_id_no_encontrado

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'id_error': id_error,
        'datos': {
            'denominacion': denominacion,
            'codigo_tipo_documento': codigo_tipo_documento,
        }
    }

    return resultado
