"""Módulo para la verificación gráfica cruzada entre XML y PDF usando IA Innti.

Extrae datos clave del XML, convierte el PDF a imagen y solicita a la IA
validar visualmente que la información coincida.
"""

import base64
import json
import logging
from io import BytesIO
from pathlib import Path

import fitz  # PyMuPDF
import httpx
from lxml import etree
from pdf2image import convert_from_path
from PIL import Image

from config import get_config, load_yaml_config
from core.python.utils.validacion import extraer_texto_xpath, parsear_decimal_2dp

logger = logging.getLogger(__name__)

_settings = load_yaml_config('settings.yaml')
_llm_cfg = _settings.get('llm', {})

_LLM_BASE_URL = get_config('LLM_BASE_URL', '')
_LLM_API_KEY = get_config('LLM_API_KEY', '')
_LLM_MODEL = get_config('LLM_MODEL', 'gpt-4o')  # Se recomienda un modelo multimodal
_TIMEOUT = int(get_config('LLM_TIMEOUT', 60))

NAMESPACES = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
}


def _extraer_datos_clave_xml(xml_factura: etree._Element) -> dict:
    """Extrae campos críticos del XML para la comparación visual."""
    
    # 1. Identificación
    id_factura = extraer_texto_xpath(xml_factura, './cbc:ID', NAMESPACES)
    cufe = extraer_texto_xpath(xml_factura, './cbc:UUID', NAMESPACES)
    fecha = extraer_texto_xpath(xml_factura, './cbc:IssueDate', NAMESPACES)
    
    # 2. Emisor
    xpath_emisor = './cac:AccountingSupplierParty/cac:Party'
    nombre_emisor = (
        extraer_texto_xpath(xml_factura, f'{xpath_emisor}/cac:PartyName/cbc:Name', NAMESPACES) or
        extraer_texto_xpath(xml_factura, f'{xpath_emisor}/cac:PartyLegalEntity/cbc:RegistrationName', NAMESPACES)
    )
    nit_emisor = extraer_texto_xpath(xml_factura, f'{xpath_emisor}/cac:PartyTaxScheme/cbc:CompanyID', NAMESPACES)
    
    # 3. Totales
    nodo_payable = xml_factura.xpath('./cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces=NAMESPACES)
    total_pagar = nodo_payable[0].text if nodo_payable else "0.00"
    moneda = nodo_payable[0].get('currencyID') if nodo_payable else "COP"

    return {
        "numero_factura": id_factura,
        "cufe": cufe,
        "fecha_emision": fecha,
        "emisor": {
            "nombre": nombre_emisor,
            "nit": nit_emisor
        },
        "total": {
            "monto": total_pagar,
            "moneda": moneda
        }
    }


def _convertir_pdf_a_base64_img(ruta_pdf: Path) -> str:
    """Convierte la primera página del PDF a una imagen base64 (PNG)."""
    paginas = convert_from_path(ruta_pdf, first_page=1, last_page=1)
    if not paginas:
        raise ValueError("No se pudo convertir el PDF a imagen")
    
    img = paginas[0]
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def _extraer_texto_local(ruta_pdf: Path) -> str:
    """Extrae texto de la capa digital del PDF (ultra rápido)."""
    try:
        doc = fitz.open(ruta_pdf)
        texto = "".join([pagina.get_text() for pagina in doc])
        return texto
    except Exception as e:
        logger.error(f"Error en extracción local: {e}")
        return ""


def _validar_datos_en_texto(datos_xml: dict, texto_pdf: str) -> bool:
    """Verifica la presencia de datos clave en el texto extraído."""
    if not texto_pdf:
        return False
    
    texto_norm = texto_pdf.lower()
    
    # Normalización de montos
    total_xml = datos_xml['total']['monto'].replace('.', '').replace(',', '')
    total_pdf_clean = texto_norm.replace('.', '').replace(',', '')
    
    nit = (datos_xml['emisor']['nit'] or '').lower()
    numero = (datos_xml['numero_factura'] or '').lower()
    
    # Búsqueda de tokens principales
    check_total = total_xml in total_pdf_clean
    check_nit = nit in texto_norm if nit else True
    check_numero = numero in texto_norm if numero else True
    
    return all([check_total, check_nit, check_numero])


async def _validar_con_ia_innti(xml_factura: etree._Element, ruta_pdf: Path, datos_xml: dict) -> bool:
    """Realiza la validación visual mediante IA Innti."""
    if not _LLM_BASE_URL or not _LLM_API_KEY:
        logger.warning("IA Innti no configurada para validación gráfica. Omitiendo.")
        return True

    try:
        img_b64 = _convertir_pdf_a_base64_img(ruta_pdf)
    except Exception as e:
        logger.error(f"Error al procesar PDF para validación visual: {e}")
        return False

    prompt = (
        "Actúa como un auditor tributario experto en Colombia. "
        "Se te proporciona una imagen de una factura y los datos extraídos de su XML oficial.\n\n"
        "DATOS DEL XML:\n"
        f"{json.dumps(datos_xml, indent=2)}\n\n"
        "TAREA:\n"
        "1. Verifica si el Número de Factura, CUFE, Fecha, NIT del Emisor y Total coinciden visualmente.\n"
        "2. Responde ÚNICAMENTE en formato JSON con la siguiente estructura:\n"
        '{"coincide": boolean, "discrepancias": ["lista de errores encontrados"], "confianza": 0-1}\n'
        "Si los datos coinciden, 'discrepancias' debe ser una lista vacía."
    )

    payload = {
        "model": _LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                    }
                ]
            }
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{_LLM_BASE_URL.rstrip('/')}/v1/chat/completions",
                headers={"Authorization": f"Bearer {_LLM_API_KEY}"},
                json=payload
            )
            response.raise_for_status()
            resultado = response.json()
            
            content = resultado['choices'][0]['message']['content']
            data = json.loads(content)
            
            if not data.get("coincide", False):
                logger.error(f"Discrepancia gráfica detectada por IA: {data.get('discrepancias')}")
                return False
            
            logger.info("Validación visual por IA exitosa.")
            return True

    except Exception as e:
        logger.error(f"Error en validación gráfica con IA: {e}")
        return False


async def validar_grafica_v1(xml_factura: etree._Element, ruta_pdf: Path) -> bool:
    """Realiza la validación cruzada XML vs PDF mediante enfoque híbrido.
    
    Args:
        xml_factura: Árbol XML de la factura.
        ruta_pdf: Ruta local al archivo PDF.
        
    Returns:
        bool: True si la validación es exitosa.
    """
    datos_xml = _extraer_datos_clave_xml(xml_factura)
    
    # 1. Intento local rápido (Costo $0)
    texto_local = _extraer_texto_local(ruta_pdf)
    if _validar_datos_en_texto(datos_xml, texto_local):
        logger.info(f"Validación gráfica local exitosa para factura {datos_xml['numero_factura']}.")
        return True
    
    # 2. Escalado a IA multimodal
    logger.warning(f"Inconsistencia local o PDF imagen detectado en {datos_xml['numero_factura']}. Escalando a IA...")
    return await _validar_con_ia_innti(xml_factura, ruta_pdf, datos_xml)

