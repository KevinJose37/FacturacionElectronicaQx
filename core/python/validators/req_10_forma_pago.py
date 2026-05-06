"""Módulo que contiene funciones de validación de la forma de pago de la factura."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree
from metadata.db_metadata import IdTipoError, IdFormaPago


logger = logging.getLogger(__name__)

# Formas de pago según la resolución 000165 de 2023 (TIPO_FORMA_PAGO)
FORMAS_PAGO = {
    IdFormaPago.contado: 'Contado',
    IdFormaPago.credito: 'Crédito',
}


def validar_forma_pago_v1(xml_invoice: etree._Element | None) -> dict:
    """Valida la forma de pago de la factura electrónica según la resolución
     000165 de 2023.

    Args:
        xml_invoice: Árbol XML de la factura electrónica a validar.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si la forma de pago es válida.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con forma de pago, fecha de vencimiento, y duración.
    """

    NAMESPACES = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    resultado_validacion = False
    codigo_forma_pago = None
    nombre_forma_pago = None
    fecha_vencimiento = None
    duracion_plazo = None

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar forma de pago.'

    else:
        nodos_payment_means = xml_invoice.xpath(
            './cac:PaymentMeans', namespaces=NAMESPACES
        )

        if not nodos_payment_means:
            mensaje = 'No se encontró la sección de forma de pago (PaymentMeans).'

        else:
            payment_means = nodos_payment_means[0]

            # cbc:ID es la forma de pago (1=contado, 2=crédito)
            nodo_id = payment_means.xpath('./cbc:ID', namespaces=NAMESPACES)
            codigo_forma_pago = (
                (nodo_id[0].text or '').strip() if nodo_id else None
            )
            nombre_forma_pago = FORMAS_PAGO.get(codigo_forma_pago)

            # Fecha de vencimiento
            nodo_vencimiento = payment_means.xpath(
                './cbc:PaymentDueDate', namespaces=NAMESPACES
            )
            fecha_vencimiento = (
                (nodo_vencimiento[0].text or '').strip()
                if nodo_vencimiento else None
            )

            # Duración del plazo (PaymentTerms)
            nodo_duracion = xml_invoice.xpath(
                './cac:PaymentTerms/cbc:ReferenceEventCode',
                namespaces=NAMESPACES
            )
            duracion_plazo = (
                (nodo_duracion[0].text or '').strip()
                if nodo_duracion else None
            )

            if not codigo_forma_pago:
                mensaje = 'No se encontró el código de forma de pago (cbc:ID).'

            elif not IdFormaPago.es_codigo_valido(codigo_forma_pago):
                mensaje = (
                    f'Código de forma de pago no válido: "{codigo_forma_pago}". '
                    f'Esperado: {sorted(IdFormaPago.CODIGOS_VALIDOS)}.'
                )

            else:
                resultado_validacion = True
                mensaje = (
                    f'Forma de pago válida: {nombre_forma_pago} '
                    f'(código {codigo_forma_pago}).'
                )

                if codigo_forma_pago == IdFormaPago.credito and not fecha_vencimiento:
                    mensaje += ' ALERTA: Crédito sin fecha de vencimiento.'

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'id_error': IdTipoError.forma_pago_invalida if not resultado_validacion else None,
        'datos': {
            'codigo_forma_pago': codigo_forma_pago,
            'nombre_forma_pago': nombre_forma_pago,
            'fecha_vencimiento': fecha_vencimiento,
            'duracion_plazo': duracion_plazo,
        }
    }

    return resultado
