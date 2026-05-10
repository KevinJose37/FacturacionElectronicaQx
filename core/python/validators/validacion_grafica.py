"""Módulo de análisis gráfico cruzado entre XML y PDF usando IA Innti.

Extrae datos clave del XML, compara contra el contenido del PDF (texto nativo
o imagen con IA multimodal) y levanta una alerta de revisión humana si detecta
discrepancias.

.. important::
    Este módulo **no es motivo de rechazo** de la factura.
    Si la verificación detecta inconsistencias, dispara una alerta mediante
    ``AlertManager`` para revisión humana pero el pipeline continúa con
    ``valido=True``.
"""

from __future__ import annotations

import base64
import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import httpx
from lxml import etree
from pdf2image import convert_from_path

from config import get_config, load_yaml_config
from core.python.utils.validacion import extraer_texto_xpath

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


# ---------------------------------------------------------------------------
# Helpers internos de extracción
# ---------------------------------------------------------------------------

def _extraer_datos_clave_xml(xml_factura: etree._Element) -> dict:
    """Extrae campos críticos del XML para la comparación visual."""
    # Identificación
    id_factura = extraer_texto_xpath(xml_factura, './cbc:ID', NAMESPACES)
    cufe = extraer_texto_xpath(xml_factura, './cbc:UUID', NAMESPACES)
    fecha = extraer_texto_xpath(xml_factura, './cbc:IssueDate', NAMESPACES)

    # Emisor
    xpath_emisor = './cac:AccountingSupplierParty/cac:Party'
    nombre_emisor = (
        extraer_texto_xpath(xml_factura, f'{xpath_emisor}/cac:PartyName/cbc:Name', NAMESPACES)
        or extraer_texto_xpath(
            xml_factura,
            f'{xpath_emisor}/cac:PartyLegalEntity/cbc:RegistrationName',
            NAMESPACES,
        )
    )
    nit_emisor = extraer_texto_xpath(
        xml_factura, f'{xpath_emisor}/cac:PartyTaxScheme/cbc:CompanyID', NAMESPACES
    )

    # Totales
    nodo_payable = xml_factura.xpath(
        './cac:LegalMonetaryTotal/cbc:PayableAmount', namespaces=NAMESPACES
    )
    total_pagar = nodo_payable[0].text if nodo_payable else '0.00'
    moneda = nodo_payable[0].get('currencyID') if nodo_payable else 'COP'

    return {
        'numero_factura': id_factura,
        'cufe': cufe,
        'fecha_emision': fecha,
        'emisor': {'nombre': nombre_emisor, 'nit': nit_emisor},
        'total': {'monto': total_pagar, 'moneda': moneda},
    }


def _convertir_pdf_a_base64_img(ruta_pdf: Path) -> str:
    """Convierte la primera página del PDF a una imagen PNG en base64."""
    paginas = convert_from_path(ruta_pdf, first_page=1, last_page=1)
    if not paginas:
        raise ValueError('No se pudo convertir el PDF a imagen')
    buffered = BytesIO()
    paginas[0].save(buffered, format='PNG')
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def _extraer_texto_local(ruta_pdf: Path) -> str:
    """Extrae texto de la capa digital del PDF mediante PyMuPDF."""
    try:
        doc = fitz.open(ruta_pdf)
        return ''.join(pagina.get_text() for pagina in doc)
    except Exception as e:
        logger.error('Error en extracción local de PDF %s: %s', ruta_pdf, e)
        return ''


def _validar_datos_en_texto(datos_xml: dict, texto_pdf: str) -> tuple[bool, list[str]]:
    """Verifica la presencia de datos clave en el texto extraído.

    Returns:
        Tupla ``(todos_ok, campos_fallidos)``.
    """
    if not texto_pdf:
        return False, ['numero_factura', 'nit_emisor', 'total']

    texto_norm = texto_pdf.lower()
    fallidos: list[str] = []

    total_xml = datos_xml['total']['monto'].replace('.', '').replace(',', '')
    total_pdf_clean = texto_norm.replace('.', '').replace(',', '')
    if total_xml not in total_pdf_clean:
        fallidos.append('total')

    nit = (datos_xml['emisor']['nit'] or '').lower()
    if nit and nit not in texto_norm:
        fallidos.append('nit_emisor')

    numero = (datos_xml['numero_factura'] or '').lower()
    if numero and numero not in texto_norm:
        fallidos.append('numero_factura')

    return len(fallidos) == 0, fallidos


# ---------------------------------------------------------------------------
# Análisis IA multimodal (no bloqueante)
# ---------------------------------------------------------------------------

async def _analizar_con_ia_innti(
    ruta_pdf: Path, datos_xml: dict
) -> dict:
    """Analiza visualmente el PDF mediante IA Innti.

    Returns:
        Diccionario ``{'coincide': bool, 'discrepancias': list, 'confianza': float}``.
        En caso de error retorna ``coincide=False`` con la descripción del fallo.
    """
    if not _LLM_BASE_URL or not _LLM_API_KEY:
        logger.warning('IA Innti no configurada para análisis gráfico. Omitiendo.')
        return {'coincide': True, 'discrepancias': [], 'confianza': 0.0, 'omitido': True}

    try:
        img_b64 = _convertir_pdf_a_base64_img(ruta_pdf)
    except Exception as e:
        logger.error('Error al convertir PDF a imagen para análisis visual: %s', e)
        return {'coincide': False, 'discrepancias': [f'No se pudo procesar el PDF: {e}'], 'confianza': 0.0}

    prompt = (
        'Actúa como un auditor tributario experto en Colombia. '
        'Se te proporciona una imagen de una factura y los datos extraídos de su XML oficial.\n\n'
        'DATOS DEL XML:\n'
        f'{json.dumps(datos_xml, indent=2, ensure_ascii=False)}\n\n'
        'TAREA:\n'
        '1. Verifica si el Número de Factura, CUFE, Fecha, NIT del Emisor y Total coinciden visualmente.\n'
        '2. Responde ÚNICAMENTE en formato JSON con la siguiente estructura:\n'
        '{"coincide": boolean, "discrepancias": ["lista de errores encontrados"], "confianza": 0-1}\n'
        "Si los datos coinciden, 'discrepancias' debe ser una lista vacía."
    )

    payload = {
        'model': _LLM_MODEL,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64}'}},
                ],
            }
        ],
        'temperature': 0.0,
        'response_format': {'type': 'json_object'},
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.post(
                f"{_LLM_BASE_URL.rstrip('/')}/v1/chat/completions",
                headers={'Authorization': f'Bearer {_LLM_API_KEY}'},
                json=payload,
            )
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']
            data = json.loads(content)
            return {
                'coincide': bool(data.get('coincide', True)),
                'discrepancias': data.get('discrepancias', []),
                'confianza': float(data.get('confianza', 1.0)),
            }
    except Exception as e:
        logger.error('Error en análisis gráfico con IA Innti: %s', e)
        return {'coincide': False, 'discrepancias': [f'Error de comunicación con IA: {e}'], 'confianza': 0.0}


# ---------------------------------------------------------------------------
# Punto de entrada público
# ---------------------------------------------------------------------------

async def analizar_representacion_grafica(
    xml_factura: etree._Element,
    ruta_pdf: Path,
    alert_manager=None,
    adjunto_id: Optional[int] = None,
    correo_id: Optional[int] = None,
) -> dict:
    """Analiza la representación gráfica (PDF) contra el XML de la factura.

    Enfoque híbrido en cascada:

    1. **Extracción local** (PyMuPDF, costo $0): busca datos clave en el texto
       digital del PDF.
    2. **IA Innti** (fallback multimodal): si el PDF es una imagen o la
       extracción local falla, envía una captura a la IA para verificación visual.

    .. important::
        Esta función **nunca rechaza la factura**. Si detecta discrepancias,
        levanta una alerta de revisión humana a través del ``alert_manager``
        proporcionado. El campo ``requiere_revision_humana`` indica si se
        disparó la alerta.

    Args:
        xml_factura: Árbol XML de la factura (ya parseado).
        ruta_pdf: Ruta local al archivo PDF.
        alert_manager: Instancia de ``AlertManager`` para notificación.
            Si es ``None``, la alerta se loguea pero no se envía.
        adjunto_id: ID del adjunto PDF en BD (para la alerta).
        correo_id: ID del correo en BD (para la alerta).

    Returns:
        ``{'valido': True, 'mensaje': str, 'datos': dict,
           'requiere_revision_humana': bool}``
    """
    datos_xml = _extraer_datos_clave_xml(xml_factura)
    num_factura = datos_xml.get('numero_factura', 'DESCONOCIDO')

    # Nivel 1: extracción de texto local
    texto_local = _extraer_texto_local(ruta_pdf)
    ok_local, campos_fallidos = _validar_datos_en_texto(datos_xml, texto_local)

    if ok_local:
        logger.info(
            'Análisis gráfico local exitoso para factura %s.', num_factura
        )
        return {
            'valido': True,
            'mensaje': f'Representación gráfica verificada localmente para factura {num_factura}.',
            'datos': {'metodo': 'local', 'campos_fallidos': []},
            'requiere_revision_humana': False,
        }

    # Nivel 2: escalado a IA multimodal
    logger.warning(
        'Verificación local incompleta en factura %s (campos: %s). Escalando a IA.',
        num_factura, campos_fallidos,
    )
    resultado_ia = await _analizar_con_ia_innti(ruta_pdf, datos_xml)

    if resultado_ia.get('omitido'):
        # IA no configurada: registrar observación sin alerta
        return {
            'valido': True,
            'mensaje': 'IA Innti no configurada; análisis gráfico omitido.',
            'datos': {'metodo': 'omitido', 'campos_fallidos': campos_fallidos},
            'requiere_revision_humana': False,
        }

    if resultado_ia['coincide']:
        logger.info('Análisis gráfico por IA exitoso para factura %s.', num_factura)
        return {
            'valido': True,
            'mensaje': f'Representación gráfica verificada por IA para factura {num_factura}.',
            'datos': {'metodo': 'ia', 'campos_fallidos': [], 'confianza': resultado_ia['confianza']},
            'requiere_revision_humana': False,
        }

    # Discrepancias detectadas — levantar alerta, NO rechazar
    discrepancias = resultado_ia['discrepancias']
    logger.warning(
        'Discrepancias gráficas detectadas en factura %s: %s',
        num_factura, discrepancias,
    )

    if alert_manager is not None:
        try:
            alert_manager.verificacion_grafica_fallida(
                num_factura=num_factura,
                metodos=['local', 'IA Innti'],
                campos_fallidos={'discrepancias': discrepancias, 'campos_locales': campos_fallidos},
                adjunto_id=adjunto_id,
                correo_id=correo_id,
            )
        except Exception as exc:
            logger.error(
                'Error al disparar alerta de verificación gráfica para %s: %s',
                num_factura, exc,
            )
    else:
        logger.warning(
            'Sin AlertManager disponible. Discrepancias gráficas en %s: %s',
            num_factura, discrepancias,
        )

    mensaje = (
        f'Discrepancias gráficas detectadas en factura {num_factura}; '
        'enviada a revisión humana. '
        f'Campos: {", ".join(discrepancias)}'
    )
    return {
        'valido': True,  # No rechaza la factura
        'mensaje': mensaje,
        'datos': {
            'metodo': 'ia',
            'discrepancias': discrepancias,
            'campos_fallidos_local': campos_fallidos,
            'confianza': resultado_ia['confianza'],
        },
        'requiere_revision_humana': True,
    }
