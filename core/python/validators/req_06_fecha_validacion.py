"""Módulo que contiene funciones de validación de la fecha de validación DIAN
 de la factura electrónica."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree
from metadata.db_metadata import IdTipoError

# Local application imports
from core.python.utils.validacion import validar_fecha_futura


logger = logging.getLogger(__name__)


def validar_fecha_validacion_dian_v1(xml_factura: etree._Element) -> dict:
    """Valida la fecha y hora de validación DIAN (expedición).
    
    Args:
        xml_factura: Árbol XML del AttachedDocument a validar.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si la fecha y hora son válidas.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con fecha y hora de validación, validador e ID.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

    XPATH_BASE = (
        './cac:ParentDocumentLineReference/cac:DocumentReference/cac:ResultOfVerification'
    )

    nodo_fecha = xml_factura.xpath(
        XPATH_BASE + '/cbc:ValidationDate',
        namespaces=NAMESPACES
    )
    nodo_hora = xml_factura.xpath(
        XPATH_BASE + '/cbc:ValidationTime',
        namespaces=NAMESPACES
    )
    nodo_validador = xml_factura.xpath(
        XPATH_BASE + '/cbc:ValidatorID',
        namespaces=NAMESPACES
    )
    nodo_codigo = xml_factura.xpath(
        XPATH_BASE + '/cbc:ValidationResultCode',
        namespaces=NAMESPACES
    )

    fecha = (nodo_fecha[0].text or '').strip() if nodo_fecha else None
    hora = (nodo_hora[0].text or '').strip() if nodo_hora else None
    validador = (nodo_validador[0].text or '').strip() if nodo_validador else None
    codigo_resultado = (nodo_codigo[0].text or '').strip() if nodo_codigo else None

    resultado_validacion = False

    if not fecha:
        mensaje = 'No se encontró la fecha de validación DIAN (ValidationDate).'

    elif not hora:
        mensaje = 'No se encontró la hora de validación DIAN (ValidationTime).'

    else:
        try:
            validacion = validar_fecha_futura(fecha, hora)
            mensaje = validacion['mensaje']
            resultado_validacion = validacion['resultado']

        except Exception:
            mensaje = (
                f'Fecha u hora de validación DIAN inválida '
                f'(ValidationDate="{fecha}", ValidationTime="{hora}").'
            )

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'id_error': IdTipoError.fecha_validacion_invalida if not resultado_validacion else None,
        'datos': {
            'fecha_validacion': fecha,
            'hora_validacion': hora,
            'validador_id': validador,
            'codigo_resultado': codigo_resultado,
        }
    }

    return resultado
