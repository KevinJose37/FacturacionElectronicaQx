"""Servicio de verificación gráfica de facturas (PDF) usando LLM.

Este servicio extrae texto de PDFs y utiliza el LLM configurado para:
1. Verificar que el PDF contenga los requisitos de representación gráfica.
2. Extraer el CUFE de un PDF huérfano.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Optional

import fitz  # PyMuPDF
import httpx

from config import get_config, load_yaml_config

logger = logging.getLogger(__name__)

_settings = load_yaml_config('settings.yaml')
_llm_cfg = _settings.get('llm', {})

_LLM_BASE_URL = get_config('LLM_BASE_URL', '')
_LLM_API_KEY = get_config('LLM_API_KEY', '')
_LLM_MODEL = get_config('LLM_MODEL', _llm_cfg.get('default_model', 'gpt-4o-mini'))
_LLM_USER_EMAIL = get_config('LLM_USER_EMAIL', '')
_LLM_TIMEOUT = int(get_config('LLM_TIMEOUT', _llm_cfg.get('timeout_seconds', 45)))


def _construir_url_llm() -> str:
    """Construye la URL completa del endpoint de chat completions."""
    base = _LLM_BASE_URL.rstrip('/')
    if not base.endswith('/v1'):
        base = f'{base}/v1'
    return f'{base}/chat/completions'


def _construir_headers() -> dict:
    """Construye los headers para la petición al LLM."""
    headers = {
        'Authorization': f'Bearer {_LLM_API_KEY}',
        'Content-Type': 'application/json',
    }
    if _LLM_USER_EMAIL:
        headers['X-OpenWebUI-User-Email'] = _LLM_USER_EMAIL
    return headers


def extraer_texto_pdf(pdf_path: str | Path) -> str:
    """Extrae el texto de un archivo PDF usando PyMuPDF.

    Args:
        pdf_path: Ruta al archivo PDF.

    Returns:
        Texto extraído del documento.
    """
    texto_completo = []
    try:
        with fitz.open(pdf_path) as doc:
            for page in doc:
                texto_completo.append(page.get_text())
        return "\n".join(texto_completo)
    except Exception as e:
        logger.error("Error al extraer texto de %s: %s", pdf_path, e)
        return ""


async def _llamar_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Hace la llamada HTTP al LLM.

    Args:
        system_prompt: Prompt de sistema.
        user_prompt: Prompt del usuario.

    Returns:
        Respuesta en texto del LLM o None si hay error.
    """
    if not _LLM_BASE_URL or not _LLM_API_KEY:
        logger.error("LLM no configurado correctamente.")
        return None

    url = _construir_url_llm()
    headers = _construir_headers()
    
    payload = {
        'model': _LLM_MODEL,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        'temperature': 0.1,  # Baja temperatura para consistencia
    }

    try:
        async with httpx.AsyncClient(timeout=_LLM_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message'].get('content', '').strip()
    except Exception as e:
        logger.error("Error al comunicarse con el LLM: %s", e)
        return None


async def verificar_requisitos_pdf(pdf_path: str | Path, datos_xml: Dict[str, Any]) -> Dict[str, Any]:
    """Verifica si el PDF contiene los datos requeridos según el XML.

    Verifica los requisitos 1-5, 8-13, 15 y 18 pasándole el texto del PDF y
    el contexto extraído del XML al LLM.

    Args:
        pdf_path: Ruta al PDF.
        datos_xml: Diccionario con los datos validados del XML.

    Returns:
        Un diccionario con el estado de validación:
        {'valido': bool, 'faltantes': list[str]}
    """
    texto_pdf = extraer_texto_pdf(pdf_path)
    if not texto_pdf.strip():
        return {'valido': False, 'faltantes': ['No se pudo extraer texto del PDF o está vacío.']}

    system_prompt = (
        "Eres un experto auditor de Facturación Electrónica DIAN en Colombia.\n"
        "Tu tarea es verificar que la representación gráfica (PDF) de una factura contenga "
        "la misma información que fue extraída de su XML oficial.\n\n"
        "Debes responder ÚNICAMENTE en formato JSON válido con la siguiente estructura:\n"
        "{\n"
        '  "valido": true/false,\n'
        '  "faltantes": ["nombre_campo_1", "nombre_campo_2"]\n'
        "}\n"
        "IMPORTANTE: en 'faltantes' coloca únicamente el NOMBRE CORTO del campo no encontrado "
        "(por ejemplo: 'NIT emisor', 'CUFE', 'Valor total'). "
        "NO incluyas los valores esperados ni explicaciones adicionales.\n"
        "Si todos los campos están presentes, 'faltantes' debe ser una lista vacía []."
    )

    datos_json = json.dumps(datos_xml, ensure_ascii=False, indent=2)
    user_prompt = (
        f"Datos del XML de la factura (valores de referencia):\n"
        f"```json\n{datos_json}\n```\n\n"
        f"Texto extraído del PDF:\n"
        f"```text\n{texto_pdf}\n```\n\n"
        "Verifica que el PDF refleje adecuadamente la información del XML.\n"
        "Devuelve un JSON estrictamente con los campos 'valido' y 'faltantes'."
    )

    respuesta_llm = await _llamar_llm(system_prompt, user_prompt)
    if not respuesta_llm:
        return {'valido': False, 'faltantes': ['Fallo en la comunicación con el LLM.']}

    try:
        # Limpiar posible markdown formatting del JSON
        if respuesta_llm.startswith("```json"):
            respuesta_llm = respuesta_llm.strip()[7:-3]
        elif respuesta_llm.startswith("```"):
            respuesta_llm = respuesta_llm.strip()[3:-3]
            
        resultado = json.loads(respuesta_llm)
        return {
            'valido': bool(resultado.get('valido', False)),
            'faltantes': resultado.get('faltantes', [])
        }
    except Exception as e:
        logger.error("El LLM retornó un formato inválido: %s", respuesta_llm)
        return {'valido': False, 'faltantes': ['El LLM no devolvió un formato JSON válido.']}


async def extraer_cufe_pdf(pdf_path: str | Path) -> Optional[str]:
    """Extrae el CUFE del texto de un PDF utilizando el LLM.

    Args:
        pdf_path: Ruta al archivo PDF huérfano.

    Returns:
        El CUFE (cadena de ~96 caracteres hex) si se encuentra, o None.
    """
    texto_pdf = extraer_texto_pdf(pdf_path)
    if not texto_pdf.strip():
        return None

    system_prompt = (
        "Eres un asistente que extrae el CUFE (Código Único de Facturación Electrónica) de textos de facturas.\n"
        "El CUFE es una cadena alfanumérica (generalmente hexadecimal) de 95 a 96 caracteres.\n"
        "Debes responder ÚNICAMENTE con el CUFE encontrado. Si no encuentras ninguno o estás inseguro, responde 'NONE'."
    )
    user_prompt = f"Busca el CUFE en el siguiente texto de un PDF:\n\n{texto_pdf}"

    respuesta = await _llamar_llm(system_prompt, user_prompt)
    
    if respuesta and respuesta.strip().upper() != 'NONE':
        cufe_limpio = respuesta.strip().replace(" ", "").replace("\n", "")
        # Validar longitud típica de un CUFE (puede variar 95-96)
        if 90 <= len(cufe_limpio) <= 100:
            return cufe_limpio
            
    return None
