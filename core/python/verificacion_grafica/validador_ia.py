"""Nivel 2: Verificación visual con IA Innti (fallback)."""

import json
import logging
import httpx

from config import get_config
from core.python.verificacion_grafica.prompts import construir_prompt_verificacion

logger = logging.getLogger(__name__)


async def verificar_con_ia(
    imagen_base64: str,
    datos_factura: dict,
    campos_fallidos: list[str],
) -> dict:
    """Envía la imagen del PDF y los datos esperados a Innti.

    Args:
        imagen_base64: Imagen PNG del PDF en base64.
        datos_factura: Datos procesados del XML.
        campos_fallidos: Lista de campos que fallaron en Nivel 1.

    Returns:
        Diccionario con resultado de la IA.
    """
    prompt = construir_prompt_verificacion(datos_factura, campos_fallidos)

    llm_base_url = get_config("LLM_BASE_URL", "").rstrip("/")
    api_key = get_config("LLM_API_KEY", "")
    model = get_config("LLM_MODEL", "gpt-4o-mini")
    timeout = int(get_config("LLM_TIMEOUT", "45"))
    
    if not llm_base_url or not api_key:
        logger.error("No hay configuración LLM válida (LLM_BASE_URL o LLM_API_KEY no están definidos)")
        return {
            "aprobado": False,
            "metodo": "IA_INNTI_FALLO_CONFIG",
            "campos": {},
            "explicacion": "Error interno: Configuración de LLM no proporcionada."
        }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{imagen_base64}"
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{llm_base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )

        response.raise_for_status()
        contenido = response.json()["choices"][0]["message"]["content"]
        resultado_ia = json.loads(contenido)
        
        campos_res = resultado_ia.get("campos", {})

        # Mapear respuesta de IA al formato interno
        todos_ok = True
        for campo in campos_fallidos:
            if not campos_res.get(campo, {}).get("presente", False):
                todos_ok = False
                break

        return {
            "aprobado": todos_ok,
            "metodo": "IA_INNTI",
            "campos": campos_res,
            "explicacion": resultado_ia.get("explicacion_general", ""),
        }
    except httpx.HTTPError as he:
        logger.error("HTTP Error conectando a IA: %s", he)
        return {
            "aprobado": False,
            "metodo": "IA_INNTI_ERROR",
            "campos": {},
            "explicacion": f"Fallo al conectar con IA: {he}"
        }
    except Exception as e:
        logger.error("Error inesperado validando con IA: %s", e)
        return {
            "aprobado": False,
            "metodo": "IA_INNTI_ERROR",
            "campos": {},
            "explicacion": f"Error parseando respuesta de IA: {e}"
        }
