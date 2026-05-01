"""Módulo que contiene funciones de validación del valor total de la factura
 electrónica."""

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import parsear_decimal_2dp


def validar_valor_total_v1(xml_factura: etree._Element) -> bool:
    """Valida el valor total de la factura electrónica.

    Args:
        xml_factura: Elemento raíz del XML de la factura.
    
    Returns:
        True si el valor total es consistente con la suma de líneas e impuestos,
         False en caso contrario.

    """
    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    }

    resultado_validacion = False

    nodo_payable = xml_factura.xpath(
        './cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces=NAMESPACES
    )
    nodo_lineas = xml_factura.xpath(
        './cac:InvoiceLine/cbc:LineExtensionAmount', namespaces=NAMESPACES
    )
    nodo_impuestos = xml_factura.xpath(
        './cac:TaxTotal/cbc:TaxAmount', namespaces=NAMESPACES
    )

    payable_amount = parsear_decimal_2dp(nodo_payable[0].text if nodo_payable else None)
    line_amounts = [parsear_decimal_2dp(nodo.text) for nodo in nodo_lineas]
    tax_amounts = [parsear_decimal_2dp(nodo.text) for nodo in nodo_impuestos]

    line_amounts = [valor for valor in line_amounts if valor is not None]
    tax_amounts = [valor for valor in tax_amounts if valor is not None]

    if payable_amount is None:
        mensaje = (
            'No se encontró el valor total a pagar en '
            'cac:LegalMonetaryTotal/cbc:PayableAmount.'
        )

    elif not line_amounts:
        mensaje = (
            'No se encontraron líneas de factura con valor en '
            'cac:InvoiceLine/cbc:LineExtensionAmount.'
        )

    else:
        total_lineas = sum(line_amounts, Decimal('0.00'))
        total_impuestos = sum(tax_amounts, Decimal('0.00'))
        total_esperado = total_lineas + total_impuestos
        total_esperado = total_esperado.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if payable_amount != total_esperado:
            mensaje = (
                'El valor total de la factura no es consistente. '
                f'Total líneas: {total_lineas}, total impuestos: {total_impuestos}, '
                f'total esperado: {total_esperado}, total encontrado: {payable_amount}.'
            )

        else:
            mensaje = (
                'Valor total de factura válido. '
                f'Total líneas: {total_lineas}, total impuestos: {total_impuestos}, '
                f'total a pagar: {payable_amount}.'
            )
            resultado_validacion = True

    enviar_log_validacion(mensaje)

    return resultado_validacion
