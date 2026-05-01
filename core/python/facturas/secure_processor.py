"""Procesador seguro de facturas electrónicas.

Realiza la validación de seguridad de los archivos ZIP recibidos,
extrae su contenido y procesa el XML principal para obtener los XMLs
embebidos (Factura y Respuesta DIAN).
"""

import logging
import tempfile
import zipfile
from pathlib import Path

from lxml import etree
from utils.security_utils import (
    escanear_con_clamav,
    validar_identidad_archivo,
    validar_integridad_zip,
)

logger = logging.getLogger(__name__)

def procesar_factura_segura(ruta_zip_str: str) -> dict | str:
    """Valida, extrae y procesa una factura electrónica desde un ZIP.

    Args:
        ruta_zip_str: Ruta al archivo ZIP descargado.

    Returns:
        Un diccionario con los contenidos si es exitoso, o un string con el error.
        El diccionario contiene: zip_path, pdf_content, xml_padre, xml_factura, xml_dian.
    """
    ruta_zip = Path(ruta_zip_str)
    resultado = 'Error desconocido'
    
    if not ruta_zip.exists():
        resultado = f'Archivo no encontrado: {ruta_zip_str}'
    elif not validar_integridad_zip(ruta_zip):
        resultado = 'Archivo ZIP corrupto o inválido'
    else:
        es_seguro, msg = escanear_con_clamav(ruta_zip)
        if not es_seguro:
            resultado = f'Seguridad: {msg}'
        else:
            try:
                resultado = _extraer_y_analizar(ruta_zip)
            except Exception as e:
                logger.exception('Error procesando factura segura')
                resultado = f'Error en procesamiento: {str(e)}'

    return resultado

def _extraer_y_analizar(ruta_zip: Path) -> dict | str:
    """Extrae el contenido del ZIP y analiza los archivos.

    Args:
        ruta_zip: Path al archivo ZIP.

    Returns:
        Diccionario con resultados o string con error.
    """
    resultado = 'Error en extracción'
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        with zipfile.ZipFile(ruta_zip, 'r') as zf:
            zf.extractall(tmp_path)
        
        archivos_extraidos = list(tmp_path.iterdir())
        xml_principal = None
        pdf_path = None
        error_seguridad = None
        
        for arch in archivos_extraidos:
            seguro_ind, msg_ind = escanear_con_clamav(arch)
            if not seguro_ind:
                error_seguridad = f'Archivo extraído infectado ({arch.name}): {msg_ind}'
                break
            
            ext = arch.suffix.lower()
            if not validar_identidad_archivo(arch, ext):
                error_seguridad = f'Identidad de archivo no coincide para {arch.name}'
                break
            
            if ext == '.xml':
                xml_principal = arch
            elif ext == '.pdf':
                pdf_path = arch

        if error_seguridad:
            resultado = error_seguridad
        elif not xml_principal or not pdf_path:
            resultado = 'El ZIP debe contener al menos un .xml y un .pdf'
        else:
            contenidos_xml = _extraer_xmls_embebidos(xml_principal)
            if isinstance(contenidos_xml, str):
                resultado = contenidos_xml
            else:
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()
                with open(xml_principal, 'rb') as f:
                    xml_padre_bytes = f.read()

                resultado = {
                    'zip_path': str(ruta_zip.absolute()),
                    'xml_padre': xml_padre_bytes,
                    'xml_factura': contenidos_xml['factura'],
                    'xml_dian': contenidos_xml['dian'],
                    'pdf_content': pdf_bytes,
                    'nombre_archivos': {
                        'xml': xml_principal.name,
                        'pdf': pdf_path.name
                    }
                }
    
    return resultado

def _extraer_xmls_embebidos(ruta_xml: Path) -> dict | str:
    """Extrae XMLs de Factura y Respuesta DIAN desde un AttachedDocument.

    Args:
        ruta_xml: Ruta al archivo XML AttachedDocument.

    Returns:
        Diccionario con 'factura' y 'dian' en bytes, o mensaje de error.
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

        xpath_factura = './/cac:Attachment/cac:ExternalReference/cbc:Description'
        factura_nodes = root.xpath(xpath_factura, namespaces=ns)
        
        xpath_dian = './/cac:ParentDocumentLineReference/cac:Attachment/cac:ExternalReference/cbc:Description'
        dian_nodes = root.xpath(xpath_dian, namespaces=ns)
        
        if not factura_nodes:
            resultado = 'No se encontró el XML de la factura embebido'
        elif not dian_nodes:
            resultado = 'No se encontró el XML de respuesta de la DIAN embebido'
        else:
            xml_factura_str = factura_nodes[0].text
            xml_dian_str = dian_nodes[0].text
            resultado = {
                'factura': xml_factura_str.strip().encode('utf-8'),
                'dian': xml_dian_str.strip().encode('utf-8')
            }
    except Exception as e:
        resultado = f'Error al parsear XML: {str(e)}'
    
    return resultado
