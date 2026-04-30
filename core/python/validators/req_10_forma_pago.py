"""Módulo que contiene funciones de validación de la forma de pago de la factura"""

# Standard library imports
from datetime import datetime

# Third-party imports
from lxml import etree


def validar_forma_pago_v1(xml_factura: etree._Element) -> bool:
    """Valida la forma de pago de la factura y su fecha de vencimiento según la
     resolución 000165 de 2023.

    Args:
        xml_factura: Elemento raíz del XML de la factura.
    
    Returns:
        True si la forma de pago y su fecha de vencimiento son válidas, False en caso
         contrario.
    
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
        mensaje = 'No se encontró cac:PaymentMeans.'
    
    else:
        nodo_id = nodo_payment_means[0].xpath(
            './cbc:ID', namespaces=NAMESPACES
        )

        nodo_due_date = nodo_payment_means[0].xpath(
            './cbc:PaymentDueDate', namespaces=NAMESPACES
        )

        forma_pago = nodo_id[0].text.strip() if nodo_id else None
        due_date = nodo_due_date[0].text.strip() if nodo_due_date else None

        if forma_pago not in ('1', '2'):
            mensaje = (
                f'Forma de pago inválida: {forma_pago}. '
                'Debe ser 1 (contado) o 2 (crédito).'
            )

        elif forma_pago == '2':  # crédito
            if not due_date:
                mensaje = (
                    'La factura es a crédito pero no tiene '
                    'cbc:PaymentDueDate.'
                )

            else:
                mensaje = (
                    f'Factura a crédito válida con plazo: {due_date}.'
                )
                resultado_validacion = True

        else:  # contado
            mensaje = 'Factura de contado válida.'
            resultado_validacion = True

    enviar_log_validacion(mensaje)

    return resultado_validacion
