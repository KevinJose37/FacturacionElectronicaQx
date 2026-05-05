"""Módulo que contiene funciones de validación del valor total de la factura."""

# Standard library imports
import logging

# Third-party imports
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from lxml import etree
from metadata.db_metadata import IdTipoError


logger = logging.getLogger(__name__)


def validar_valor_total_v1(xml_invoice: etree._Element | None) -> dict:
    """Valida el valor total de la factura electrónica según la resolución
     000165 de 2023.

    Args:
        xml_invoice: Árbol XML de la factura electrónica a validar.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si el valor total es correcto.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con los valores monetarios extraídos.
    """

    NAMESPACES = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    datos = {
        'valor_bruto': None,
        'valor_base_impuestos': None,
        'total_impuestos': None,
        'total_cargos': None,
        'total_descuentos': None,
        'valor_a_pagar': None,
        'moneda': None,
    }
    resultado_validacion = False

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar valor total.'

    else:
        xpaths = {
            'valor_bruto': './cac:LegalMonetaryTotal/cbc:LineExtensionAmount',
            'valor_base_impuestos': './cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount',
            'total_impuestos': './cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount',
            'total_cargos': './cac:LegalMonetaryTotal/cbc:ChargeTotalAmount',
            'total_descuentos': './cac:LegalMonetaryTotal/cbc:AllowanceTotalAmount',
            'valor_a_pagar': './cac:LegalMonetaryTotal/cbc:PayableAmount',
        }

        for campo, xpath in xpaths.items():
            nodos = xml_invoice.xpath(xpath, namespaces=NAMESPACES)
            if nodos and nodos[0].text:
                try:
                    valor = Decimal(nodos[0].text.strip())
                    datos[campo] = str(
                        valor.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    )
                except InvalidOperation:
                    datos[campo] = nodos[0].text.strip()

                if campo == 'valor_a_pagar':
                    moneda = nodos[0].get('currencyID')
                    if moneda:
                        datos['moneda'] = moneda

        # Verificar valor a pagar
        if datos['valor_a_pagar'] is None:
            mensaje = 'No se encontró el valor total a pagar (PayableAmount).'

        else:
            try:
                valor_a_pagar = Decimal(datos['valor_a_pagar'])

                if valor_a_pagar < Decimal('0'):
                    mensaje = f'El valor a pagar es negativo: {valor_a_pagar}.'

                else:
                    # Validar que el valor_a_pagar cuadre con la suma
                    if datos['valor_bruto'] is not None:
                        bruto = Decimal(datos['valor_bruto'])
                        cargos = Decimal(datos['total_cargos'] or '0')
                        descuentos = Decimal(datos['total_descuentos'] or '0')

                        # Sumar impuestos desde TaxTotal
                        total_tax = Decimal('0')
                        tax_totals = xml_invoice.xpath(
                            './cac:TaxTotal/cbc:TaxAmount', namespaces=NAMESPACES
                        )
                        for tt in tax_totals:
                            if tt.text and tt.text.strip():
                                try:
                                    total_tax += Decimal(tt.text.strip())
                                except InvalidOperation:
                                    pass

                        calculado = bruto + total_tax + cargos - descuentos
                        calculado_2d = calculado.quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                        diferencia = abs(calculado_2d - valor_a_pagar)

                        if diferencia > Decimal('1.00'):
                            mensaje = (
                                f'Valor a pagar ({valor_a_pagar}) difiere de la suma '
                                f'calculada ({calculado_2d}) en {diferencia}.'
                            )
                        else:
                            resultado_validacion = True
                            mensaje = (
                                f'Valor total válido: {valor_a_pagar} '
                                f'{datos["moneda"] or "COP"}.'
                            )
                    else:
                        resultado_validacion = True
                        mensaje = (
                            f'Valor a pagar presente: {valor_a_pagar}. '
                            f'Sin LineExtensionAmount para validación cruzada.'
                        )

            except InvalidOperation:
                mensaje = f'Valor a pagar no numérico: {datos["valor_a_pagar"]}.'

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'id_error': IdTipoError.valor_total_inconsistente if not resultado_validacion else None,
        'datos': datos,
    }

    return resultado
