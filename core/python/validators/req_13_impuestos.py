"""Módulo que contiene funciones de validación de los impuestos de la factura."""

# Standard library imports
import logging

# Third-party imports
from decimal import Decimal, ROUND_HALF_UP
from lxml import etree
from metadata.db_metadata import IdTipoError, IdTipoImpuesto


logger = logging.getLogger(__name__)

# Mapeo de códigos DIAN a nombres legibles (fuente: TIPO_IMPUESTO)
CODIGOS_IMPUESTOS = {
    IdTipoImpuesto.iva: 'IVA',
    IdTipoImpuesto.ic: 'IC',
    IdTipoImpuesto.ica: 'ICA',
    IdTipoImpuesto.inc: 'INC',
    IdTipoImpuesto.rete_iva: 'ReteIVA',
    IdTipoImpuesto.rete_renta: 'ReteRenta',
    IdTipoImpuesto.rete_ica: 'ReteICA',
    IdTipoImpuesto.ic_porcentual: 'IC Porcentual',
    IdTipoImpuesto.fto_horticultura: 'FtoHorticultura',
    IdTipoImpuesto.timbre: 'Timbre',
    IdTipoImpuesto.inc_bolsas: 'INC Bolsas',
    IdTipoImpuesto.in_carbono: 'INCarbono',
    IdTipoImpuesto.in_combustibles: 'INCombustibles',
    IdTipoImpuesto.sobretasa_combustibles: 'Sobretasa Combustibles',
    IdTipoImpuesto.sordicom: 'Sordicom',
    IdTipoImpuesto.ic_datos: 'IC Datos',
    IdTipoImpuesto.icl: 'ICL',
    IdTipoImpuesto.inpp: 'INPP',
    IdTipoImpuesto.ibua: 'IBUA',
    IdTipoImpuesto.icui: 'ICUI',
    IdTipoImpuesto.adv: 'ADV',
    IdTipoImpuesto.otros: 'Otros',
}


def validar_impuestos_v1(xml_invoice: etree._Element | None) -> dict:
    """Valida los impuestos de la factura electrónica según la resolución 000165
    de 2023.

    Args:
        xml_invoice: Árbol XML de la factura electrónica a validar.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si los impuestos son correctos.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con impuestos extraídos y totales.
    """

    NAMESPACES = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    resultado_validacion = False
    impuestos_extraidos = []
    total_impuestos = Decimal('0')
    errores = []

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar impuestos.'

    else:
        tax_totals = xml_invoice.xpath('./cac:TaxTotal', namespaces=NAMESPACES)

        for tt in tax_totals:
            # TaxAmount total de este grupo
            nodo_total = tt.xpath('./cbc:TaxAmount', namespaces=NAMESPACES)
            monto_total_grupo = (
                (nodo_total[0].text or '').strip() if nodo_total else None
            )
            moneda = nodo_total[0].get('currencyID') if nodo_total else None

            subtotales = tt.xpath('./cac:TaxSubtotal', namespaces=NAMESPACES)

            for st in subtotales:
                nodo_taxable = st.xpath('./cbc:TaxableAmount', namespaces=NAMESPACES)
                nodo_tax_amount = st.xpath('./cbc:TaxAmount', namespaces=NAMESPACES)
                nodo_percent = st.xpath(
                    './cac:TaxCategory/cbc:Percent', namespaces=NAMESPACES
                )
                nodo_tax_id = st.xpath(
                    './cac:TaxCategory/cac:TaxScheme/cbc:ID', namespaces=NAMESPACES
                )
                nodo_tax_name = st.xpath(
                    './cac:TaxCategory/cac:TaxScheme/cbc:Name', namespaces=NAMESPACES
                )

                codigo = (
                    (nodo_tax_id[0].text or '').strip() if nodo_tax_id else None
                )
                nombre_impuesto = (
                    (nodo_tax_name[0].text or '').strip() if nodo_tax_name else None
                )
                nombre_impuesto = nombre_impuesto or CODIGOS_IMPUESTOS.get(
                    codigo, 'Desconocido'
                )
                base_gravable = (
                    (nodo_taxable[0].text or '').strip() if nodo_taxable else None
                )
                monto = (
                    (nodo_tax_amount[0].text or '').strip()
                    if nodo_tax_amount else None
                )
                tarifa = (
                    (nodo_percent[0].text or '').strip() if nodo_percent else None
                )

                impuesto = {
                    'codigo_impuesto': codigo,
                    'nombre_impuesto': nombre_impuesto,
                    'base_gravable': base_gravable,
                    'tarifa': tarifa,
                    'valor_impuesto': monto,
                    'moneda': moneda,
                }

                if not codigo:
                    errores.append(
                        'Impuesto sin código de identificación (TaxScheme/ID).'
                    )

                if monto:
                    try:
                        total_impuestos += Decimal(monto)
                    except Exception:
                        errores.append(
                            f'Valor de impuesto no numérico: "{monto}".'
                        )

                impuestos_extraidos.append(impuesto)

        if not impuestos_extraidos:
            mensaje = 'No se encontraron impuestos (TaxTotal) en la factura.'
            # No es un error bloqueante: facturas exentas pueden no tener impuestos
            resultado_validacion = True

        elif errores:
            mensaje = 'Errores en impuestos:\n' + '\n'.join(errores)

        else:
            total_formateado = total_impuestos.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            mensaje = (
                f'Impuestos válidos: {len(impuestos_extraidos)} subtotales, '
                f'total impuestos {total_formateado}.'
            )
            resultado_validacion = True

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'id_error': IdTipoError.impuestos_invalidos if not resultado_validacion else None,
        'datos': {
            'impuestos': impuestos_extraidos,
            'total_impuestos': str(total_impuestos.quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )) if impuestos_extraidos else '0.00',
        }
    }

    return resultado
