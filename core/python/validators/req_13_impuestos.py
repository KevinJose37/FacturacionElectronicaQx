"""Módulo que contiene funciones de validación de los impuestos de la factura."""

# Third-party imports
from lxml import etree


def validar_impuestos_v1(xml_factura: etree._Element) -> bool:
    """Valida la discriminación de impuestos (IVA, INC, bolsas plásticas) y sus
    tarifas según la resolución 000165 de 2023.

    Args:
        xml_factura: Elemento raíz del XML de la factura.

    Returns:
        True si los impuestos están correctamente informados, False en caso contrario.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    }

    resultado_validacion = False

    nodos_tax_total = xml_factura.xpath('./cac:TaxTotal', namespaces=NAMESPACES)

    detalles_impuestos = []

    for tax_total in nodos_tax_total:
        subtotales = tax_total.xpath('./cac:TaxSubtotal', namespaces=NAMESPACES)

        for subtotal in subtotales:
            nodo_id = subtotal.xpath(
                './cac:TaxCategory/cac:TaxScheme/cbc:ID', namespaces=NAMESPACES
            )
            nodo_percent = subtotal.xpath(
                './cac:TaxCategory/cbc:Percent', namespaces=NAMESPACES
            )

            tax_id = nodo_id[0].text.strip() if nodo_id and nodo_id[0].text else None
            percent = (
                nodo_percent[0].text.strip()
                if nodo_percent and nodo_percent[0].text else None
            )

            if tax_id and percent:
                detalles_impuestos.append(f'{tax_id}:{percent}')

            else:
                detalles_impuestos.append(None)

    if not nodos_tax_total:
        mensaje = 'No se encontró información de impuestos (cac:TaxTotal).'

    elif not detalles_impuestos:
        mensaje = 'No se encontraron subtotales de impuestos (cac:TaxSubtotal).'

    elif any(detalle is None for detalle in detalles_impuestos):
        mensaje = (
            'Existen impuestos sin identificación o tarifa '
            '(cbc:ID o cbc:Percent).'
        )

    else:
        resultado_validacion = True
        mensaje = (
            'Se informó la discriminación de impuestos con sus tarifas. '
            f'Detalle: {", ".join(detalles_impuestos)}.'
        )

    enviar_log_validacion(mensaje)

    return resultado_validacion
