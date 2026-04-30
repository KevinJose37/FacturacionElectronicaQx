"""Módulo que contiene funciones de validación de la fecha de generación de la factura
 electrónica."""

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import validar_fecha_futura


def validar_fecha_validacion_dian_v1(xml_factura: etree._Element) -> bool:
    """Valida la fecha y hora de validación DIAN (expedición).
    
    Args:
        xml_factura: Árbol XML del AttachedDocument a validar.

    Reglas:
    - Debe existir ValidationDate
    - Debe existir ValidationTime
    - Ambos deben tener formato válido (ISO 8601)

    Retorna:
        True si la fecha y hora son válidas, False en caso contrario.
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

    fecha = (nodo_fecha[0].text or '').strip() if nodo_fecha else None
    hora = (nodo_hora[0].text or '').strip() if nodo_hora else None

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

    enviar_log_validacion(mensaje)

    return resultado_validacion
