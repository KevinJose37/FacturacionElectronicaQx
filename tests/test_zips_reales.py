import asyncio
import logging
import zipfile
import tempfile
import sys
from pathlib import Path
from lxml import etree

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger(__name__)

# Agregar el directorio raíz al path para importar los módulos correctamente
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from core.python.verificacion_grafica.controlador import verificar_representacion_grafica
from core.python.utils.extractor_xml import extraer_todos_los_requisitos

NAMESPACES = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
}

def extraer_datos_xml(xml_path: Path) -> dict:
    """Extrae los campos requeridos para la validación gráfica desde el XML."""
    tree = etree.parse(str(xml_path))
    root = tree.getroot()
    
    # Si es un AttachedDocument, el Invoice real está dentro de cbc:Description como CDATA
    if "AttachedDocument" in root.tag:
        logger.info("Detectado contenedor AttachedDocument. Extrayendo Invoice interna...")
        desc_node = root.xpath(".//cbc:Description", namespaces=NAMESPACES)
        if desc_node and desc_node[0].text:
            try:
                # El texto dentro de Description es el XML de la Invoice
                inner_xml = desc_node[0].text.strip()
                root = etree.fromstring(inner_xml.encode('utf-8'))
            except Exception as e:
                logger.error(f"Error parseando Invoice interna: {e}")
    
    return extraer_todos_los_requisitos(root)

async def probar_zip(zip_path: Path):
    logger.info(f"--- Probando ZIP: {zip_path.name} ---")
    
    with tempfile.TemporaryDirectory() as tmpdirname:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdirname)
        
        tmp_dir = Path(tmpdirname)
        xml_files = list(tmp_dir.glob("*.xml"))
        pdf_files = list(tmp_dir.glob("*.pdf"))
        
        if not xml_files or not pdf_files:
            logger.error(f"ZIP {zip_path.name} no contiene par XML y PDF")
            return
            
        xml_path = xml_files[0]
        pdf_path = pdf_files[0]
        
        logger.info(f"XML encontrado: {xml_path.name}")
        logger.info(f"PDF encontrado: {pdf_path.name}")
        
        datos_factura = extraer_datos_xml(xml_path)
        logger.info(f"Datos extraídos del XML: {datos_factura}")
        
        resultado = await verificar_representacion_grafica(pdf_path, datos_factura)
        
        logger.info("=== RESULTADO DE LA VERIFICACIÓN ===")
        logger.info(f"Aprobado: {resultado['aprobado']}")
        logger.info(f"Método utilizado: {resultado['metodo']}")
        
        if not resultado['aprobado']:
            logger.warning("Fallo en la verificación:")
            for campo, info in resultado.get('campos', {}).items():
                if not info.get('encontrado'):
                    logger.warning(f"  - {campo}: No encontrado/Discrepancia")
            
            if 'observacion' in resultado:
                logger.info(f"  - Explicación: {resultado['observacion']}")
            elif 'explicacion_general' in resultado:
                logger.info(f"  - Explicación Innti: {resultado['explicacion_general']}")

async def main():
    zips = [
        Path("tests/validaciones/AttachedDocument.zip"),
        Path("tests/validaciones/z09004201220072622181258.zip")
    ]
    
    for zip_p in zips:
        if zip_p.exists():
            await probar_zip(zip_p)
        else:
            logger.error(f"No se encontró el archivo: {zip_p}")

if __name__ == "__main__":
    asyncio.run(main())
