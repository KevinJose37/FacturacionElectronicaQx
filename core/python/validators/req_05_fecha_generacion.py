"""Módulo que contiene funciones de validación de la fecha de generación de la factura
 electrónica."""

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import validar_fecha_futura


def validar_fecha_generacion_v1(xml_factura: etree._Element) -> bool:
    """Valida la fecha y hora de generación de la factura electrónica.
    
    Args:
        xml_factura: Árbol XML de la factura electrónica a validar.

    Reglas:
    - Debe existir IssueDate
    - Debe existir IssueTime
    - Ambos deben tener formato válido (ISO 8601)

    Retorna:
        True si la fecha y hora son válidas, False en caso contrario.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    nodo_fecha = xml_factura.xpath('./cbc:IssueDate', namespaces=NAMESPACES)
    nodo_hora = xml_factura.xpath('./cbc:IssueTime', namespaces=NAMESPACES)

    fecha = (nodo_fecha[0].text or '').strip() if nodo_fecha else None
    hora = (nodo_hora[0].text or '').strip() if nodo_hora else None

    resultado_validacion = False

    if not fecha:
        mensaje = 'No se encontró la fecha de generación (IssueDate).'

    elif not hora:
        mensaje = 'No se encontró la hora de generación (IssueTime).'

    else:
        try:
            validacion = validar_fecha_futura(fecha, hora)
            mensaje = validacion['mensaje']
            resultado_validacion = validacion['resultado']

        except Exception:
            mensaje = (
                f'Fecha u hora de generación inválida '
                f'(IssueDate="{fecha}", IssueTime="{hora}").'
            )

    enviar_log_validacion(mensaje)

    return resultado_validacion
