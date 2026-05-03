"""Módulo que contiene funciones de validación de la calidad tributaria del emisor."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree


logger = logging.getLogger(__name__)

# Responsabilidades fiscales según catálogo DIAN
RESPONSABILIDADES_FISCALES = {
    'O-13': 'Gran contribuyente',
    'O-15': 'Autorretenedor',
    'O-23': 'Agente de retención del IVA',
    'O-47': 'Régimen simple de tributación',
    'R-99-PN': 'No aplica – Otros',
    'ZZ': 'No responsable',
    'ZA': 'IVA',
}


def validar_calidad_tributaria_v1(xml_invoice: etree._Element | None) -> dict:
    """Valida la calidad tributaria del emisor según la resolución 000165 de 2023.

    Args:
        xml_invoice: Árbol XML de la factura electrónica a validar.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si la calidad tributaria es válida.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con lista de responsabilidades fiscales del emisor y
            adquiriente.
    """

    NAMESPACES = {
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
    }

    resultado_validacion = False
    responsabilidades_emisor = []
    responsabilidades_adquiriente = []

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar calidad tributaria.'

    else:
        # Extraer responsabilidades fiscales del emisor
        nodos_emisor = xml_invoice.xpath(
            './cac:AccountingSupplierParty/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode',
            namespaces=NAMESPACES
        )

        for nodo in nodos_emisor:
            texto = (nodo.text or '').strip()
            if texto:
                # Puede ser una lista separada por ';'
                for codigo in texto.split(';'):
                    codigo = codigo.strip()
                    if codigo:
                        responsabilidades_emisor.append({
                            'codigo': codigo,
                            'descripcion': RESPONSABILIDADES_FISCALES.get(
                                codigo, 'Código no catalogado'
                            ),
                        })

        # Extraer responsabilidades fiscales del adquiriente
        nodos_adquiriente = xml_invoice.xpath(
            './cac:AccountingCustomerParty/cac:Party/cac:PartyTaxScheme/cbc:TaxLevelCode',
            namespaces=NAMESPACES
        )

        for nodo in nodos_adquiriente:
            texto = (nodo.text or '').strip()
            if texto:
                for codigo in texto.split(';'):
                    codigo = codigo.strip()
                    if codigo:
                        responsabilidades_adquiriente.append({
                            'codigo': codigo,
                            'descripcion': RESPONSABILIDADES_FISCALES.get(
                                codigo, 'Código no catalogado'
                            ),
                        })

        if not responsabilidades_emisor:
            mensaje = (
                'No se encontró la calidad tributaria del emisor '
                '(TaxLevelCode en AccountingSupplierParty).'
            )
        else:
            resultado_validacion = True
            codigos = ', '.join(
                r['codigo'] for r in responsabilidades_emisor
            )
            mensaje = f'Calidad tributaria válida del emisor: {codigos}.'

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'datos': {
            'responsabilidades_emisor': responsabilidades_emisor,
            'responsabilidades_adquiriente': responsabilidades_adquiriente,
        }
    }

    return resultado
