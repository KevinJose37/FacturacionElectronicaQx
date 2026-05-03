"""Módulo que contiene funciones de validación del medio de pago de la factura."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree


logger = logging.getLogger(__name__)

# Medios de pago según catálogo DIAN (basado en ISO 4217/UN/EDIFACT TRED 4461)
MEDIOS_PAGO = {
    '1': 'Instrumento no definido',
    '2': 'Crédito ACH',
    '3': 'Débito ACH',
    '10': 'Efectivo',
    '20': 'Cheque',
    '30': 'Transferencia crédito',
    '31': 'Transferencia débito',
    '32': 'Concentración flujo de efectivo',
    '42': 'Transferencia bancaria',
    '47': 'Transferencia entre cuentas',
    '48': 'Tarjeta crédito',
    '49': 'Tarjeta débito',
    'ZZZ': 'Mutuo acuerdo',
}


def validar_medio_pago_v1(
    xml_invoice: etree._Element | None,
    codigo_forma_pago: str | None = None,
) -> dict:
    """Valida el medio de pago de la factura electrónica según la resolución
     000165 de 2023.

    Args:
        xml_invoice: Árbol XML de la factura electrónica a validar.
        codigo_forma_pago: Código de forma de pago (1=contado, 2=crédito).
            Si es contado, el medio de pago es obligatorio.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si el medio de pago es válido.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con medio de pago extraído.
    """

    NAMESPACES = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    resultado_validacion = False
    codigo_medio_pago = None
    nombre_medio_pago = None

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar medio de pago.'

    else:
        # PaymentMeansCode contiene el código del medio de pago
        nodos_payment_means = xml_invoice.xpath(
            './cac:PaymentMeans/cbc:PaymentMeansCode',
            namespaces=NAMESPACES
        )

        codigo_medio_pago = (
            (nodos_payment_means[0].text or '').strip()
            if nodos_payment_means else None
        )
        nombre_medio_pago = MEDIOS_PAGO.get(codigo_medio_pago)

        if not codigo_medio_pago:
            es_contado = codigo_forma_pago == '1'

            if es_contado:
                mensaje = (
                    'No se encontró el medio de pago (PaymentMeansCode). '
                    'Es obligatorio para pagos de contado.'
                )
            else:
                # Para crédito, el medio de pago es opcional
                mensaje = (
                    'No se encontró el medio de pago (PaymentMeansCode). '
                    'No aplica para pago a crédito.'
                )
                resultado_validacion = True

        elif codigo_medio_pago not in MEDIOS_PAGO:
            mensaje = (
                f'Código de medio de pago no reconocido: "{codigo_medio_pago}".'
            )

        else:
            resultado_validacion = True
            mensaje = (
                f'Medio de pago válido: {nombre_medio_pago} '
                f'(código {codigo_medio_pago}).'
            )

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'datos': {
            'codigo_medio_pago': codigo_medio_pago,
            'nombre_medio_pago': nombre_medio_pago,
        }
    }

    return resultado
