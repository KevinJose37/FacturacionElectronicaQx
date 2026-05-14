"""Utilidades para extracción y parseo de XMLs de facturas electrónicas.

Centraliza la lógica de extracción de XMLs embebidos (Invoice y
ApplicationResponse) desde el AttachedDocument, evitando duplicación
entre el procesador seguro y el procesador de facturas.
"""

import logging
from pathlib import Path
from typing import Optional

from lxml import etree


logger = logging.getLogger(__name__)


def extraer_xmls_embebidos(ruta_xml: Path) -> dict | str:
    """Extrae XMLs de Factura y Respuesta DIAN desde un AttachedDocument.

    Busca dentro del AttachedDocument los nodos CDATA que contienen
    el Invoice (factura) y el ApplicationResponse (validación DIAN).

    Args:
        ruta_xml: Ruta al archivo XML AttachedDocument.

    Returns:
        Diccionario con 'invoice' y 'applicationresponse' en bytes,
        o mensaje de error como string.
    """
    resultado = 'Error al procesar XML embebido'
    try:
        parser = etree.XMLParser(recover=True, remove_comments=True)
        tree = etree.parse(str(ruta_xml), parser)
        root = tree.getroot()

        ns = {
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'
        }

        xpath_factura = (
            './/cac:Attachment/cac:ExternalReference/cbc:Description'
            '[not(ancestor::cac:ParentDocumentLineReference)]'
        )
        factura_nodes = root.xpath(xpath_factura, namespaces=ns)

        xpath_dian = (
            './/cac:ParentDocumentLineReference//cac:Attachment'
            '/cac:ExternalReference/cbc:Description'
        )
        dian_nodes = root.xpath(xpath_dian, namespaces=ns)

        res_dict = {}
        
        if factura_nodes:
            xml_factura_str = factura_nodes[0].text
            res_dict['invoice'] = xml_factura_str.strip().encode('utf-8')
        else:
            logger.warning('No se encontró el XML de la factura embebido en el AttachedDocument.')
            
        if dian_nodes:
            xml_dian_str = dian_nodes[0].text
            res_dict['applicationresponse'] = xml_dian_str.strip().encode('utf-8')
        else:
            logger.warning('No se encontró el XML de respuesta de la DIAN embebido en el AttachedDocument.')
            
        if not res_dict:
            resultado = 'No se encontraron XMLs embebidos (ni Invoice ni ApplicationResponse)'
        else:
            resultado = res_dict
    except Exception as e:
        resultado = f'Error al parsear XML: {str(e)}'

    return resultado


def parsear_xml_bytes(contenido_bytes: bytes) -> Optional[etree._Element]:
    """Parsea contenido XML en bytes y retorna el elemento raíz.

    Args:
        contenido_bytes: Contenido XML como bytes.

    Returns:
        Elemento raíz del XML, o None si hubo error de parseo.
    """
    arbol_xml = None

    try:
        parser = etree.XMLParser(recover=True, remove_comments=True)
        arbol_xml = etree.fromstring(contenido_bytes, parser)
    except etree.XMLSyntaxError as error:
        logger.error('Error de sintaxis al parsear XML: %s', error)
    except Exception as e:
        logger.error('Error inesperado al parsear XML: %s', e)

    return arbol_xml
