"""Módulo que contiene funciones de validación de la calidad tributaria del emisor de la
 factura."""
 
# Third-party imports
from lxml import etree


def validar_calidad_tributaria_v1(xml_factura: etree._Element) -> bool:
    """Valida la calidad tributaria del facturador electrónico según la resolución 000165
     de 2023.

    Args:
        xml_factura: Elemento raíz del XML de la factura.

    Returns:
        True si el XML informa la calidad tributaria del vendedor, False en caso
        contrario.

    """
    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    }

    resultado_validacion = False

    nodos_tax_level_code = xml_factura.xpath(
        './cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode',
        namespaces=NAMESPACES,
    )

    valores_tax_level_code = [
        nodo.text.strip() for nodo in nodos_tax_level_code
        if nodo is not None and nodo.text and nodo.text.strip()
    ]

    if not valores_tax_level_code:
        mensaje = (
            'No se informó la calidad tributaria del facturador electrónico '
            '(cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode).'
        )
    else:
        resultado_validacion = True
        mensaje = (
            'Se informó la calidad tributaria del facturador electrónico. '
            f'Valor(es): {", ".join(valores_tax_level_code)}.'
        )

    enviar_log_validacion(mensaje)

    return resultado_validacion
