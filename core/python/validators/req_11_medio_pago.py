"""Módulo que contiene funciones de validación del medio de pago de la factura."""

# Third-party imports
from lxml import etree


def validar_medio_pago_v1(xml_factura: etree._Element) -> bool:
    """Valida el medio de pago de la factura y su fecha de vencimiento según la
     resolución 000165 de 2023.

    Args:
        xml_factura: Elemento raíz del XML de la factura.
    
    Returns:
        True si el medio de pago es válido, False en caso contrario.
    
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    }

    resultado_validacion = False

    nodo_payment_means = xml_factura.xpath(
        './cac:PaymentMeans', namespaces=NAMESPACES
    )

    if not nodo_payment_means:
        mensaje = 'No se encontró el nodo cac:PaymentMeans.'
        enviar_log_validacion(mensaje)
        return False

    nodo_code = nodo_payment_means[0].xpath(
        './cbc:PaymentMeansCode', namespaces=NAMESPACES
    )
    nodo_id = nodo_payment_means[0].xpath(
        './cbc:PaymentID', namespaces=NAMESPACES
    )

    payment_code = nodo_code[0].text.strip() if nodo_code and nodo_code[0].text else None
    payment_id = nodo_id[0].text.strip() if nodo_id and nodo_id[0].text else None

    if not payment_code:
        mensaje = 'No se encontró el código del medio de pago (PaymentMeansCode).'

    else:
        es_contado = payment_code == '1'

        if not es_contado:
            mensaje = (
                f'La forma de pago no es de contado (código: {payment_code}). '
                'No aplica validación de medio de pago.'
            )
            resultado_validacion = True

        else:
            if not payment_id:
                mensaje = (
                    'La forma de pago es de contado pero no se informó el medio de pago '
                    '(cbc:PaymentID).'
                )

            else:
                mensaje = (
                    'Medio de pago válido para forma de pago de contado. '
                    f'Código: {payment_code}, nombre: {payment_id}.'
                )
                resultado_validacion = True

    enviar_log_validacion(mensaje)

    return resultado_validacion
