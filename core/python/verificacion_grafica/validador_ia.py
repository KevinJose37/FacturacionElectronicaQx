"""Nivel 2: Verificación visual con IA Innti (fallback)."""

import json
import logging
import httpx
import asyncio
import time
import hashlib

from config import get_config
from core.python.verificacion_grafica.prompts import construir_prompt_verificacion

logger = logging.getLogger(__name__)

# Cache en memoria: hash_img -> resultado_dict
_cache_resultados_ia = {}

# Circuit Breaker state
_fallos_consecutivos = 0
_ultimo_fallo_timestamp = 0.0
CIRCUIT_BREAKER_LIMITE = 5
CIRCUIT_BREAKER_TIEMPO_RECOVERY = 300.0  # 5 minutos en segundos


def _registrar_fallo():
    global _fallos_consecutivos, _ultimo_fallo_timestamp
    _fallos_consecutivos += 1
    _ultimo_fallo_timestamp = time.time()
    logger.warning("Fallo registrado en IA Innti. Fallos consecutivos: %d", _fallos_consecutivos)


def _registrar_exito():
    global _fallos_consecutivos, _ultimo_fallo_timestamp
    if _fallos_consecutivos > 0:
        logger.info("Conexión con IA Innti restablecida con éxito. Reseteando Circuit Breaker.")
    _fallos_consecutivos = 0
    _ultimo_fallo_timestamp = 0.0


async def verificar_con_ia(
    imagen_base64: str | list[str],
    datos_factura: dict,
    campos_fallidos: list[str],
) -> dict:
    """Envía la(s) imagen(es) del PDF y los datos esperados a Innti.

    Soporta una única imagen base64 o una lista de imágenes base64 para PDFs multipágina.

    Args:
        imagen_base64: Imagen JPEG del PDF en base64 (o lista de imágenes).
        datos_factura: Datos procesados del XML.
        campos_fallidos: Lista de campos que fallaron en Nivel 1.

    Returns:
        Diccionario con resultado de la IA.
    """
    global _fallos_consecutivos, _ultimo_fallo_timestamp

    # Normalizar entrada a lista
    imagenes = [imagen_base64] if isinstance(imagen_base64, str) else imagen_base64

    # 1. Verificar Circuit Breaker
    if _fallos_consecutivos >= CIRCUIT_BREAKER_LIMITE:
        tiempo_transcurrido = time.time() - _ultimo_fallo_timestamp
        if tiempo_transcurrido < CIRCUIT_BREAKER_TIEMPO_RECOVERY:
            logger.warning(
                "Circuit Breaker ACTIVO para Innti IA. Saltando llamada y derivando a revisión humana. Fallos consecutivos: %d, tiempo restante: %ds",
                _fallos_consecutivos,
                int(CIRCUIT_BREAKER_TIEMPO_RECOVERY - tiempo_transcurrido)
            )
            return {
                "aprobado": False,
                "metodo": "IA_INNTI_CIRCUIT_BREAKER",
                "campos": {},
                "explicacion": "Servicio de verificación por IA temporalmente fuera de servicio (Circuit Breaker activo)."
            }
        else:
            logger.info("Tiempo de recuperación de Circuit Breaker cumplido. Intentando conectar nuevamente...")

    # 2. Verificar Caché en Memoria
    # Calcular hash de las imágenes base64 y los campos fallidos para unicidad
    hash_input = ("".join(imagenes) + "_" + ",".join(sorted(campos_fallidos))).encode("utf-8")
    hash_val = hashlib.sha256(hash_input).hexdigest()

    if hash_val in _cache_resultados_ia:
        logger.info("Resultado de validación IA recuperado de la caché en memoria.")
        return _cache_resultados_ia[hash_val]

    prompt = construir_prompt_verificacion(datos_factura, campos_fallidos)

    llm_base_url = get_config("LLM_BASE_URL", "").rstrip("/")
    api_key = get_config("LLM_API_KEY", "")
    model = get_config("LLM_MODEL", "innti-dev")
    user_email = get_config("LLM_USER_EMAIL", "")
    timeout = int(get_config("LLM_TIMEOUT", "45"))
    
    if not llm_base_url or not api_key:
        logger.error("No hay configuración LLM válida (LLM_BASE_URL o LLM_API_KEY no están definidos)")
        return {
            "aprobado": False,
            "metodo": "IA_INNTI_FALLO_CONFIG",
            "campos": {},
            "explicacion": "Error interno: Configuración de LLM no proporcionada."
        }

    # Construir contenido del mensaje multimodal dinámicamente
    mensaje_content = [{"type": "text", "text": prompt}]
    for img in imagenes:
        mensaje_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img}"
            },
        })

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": mensaje_content,
            }
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }

    try:
        max_intentos = 3
        resultado_ok = False
        contenido = None

        for intento in range(1, max_intentos + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    if user_email:
                        headers["X-OpenWebUI-User-Email"] = user_email
                    logger.info("Enviando petición a IA (Intento %d/%d): %s/v1/chat/completions", intento, max_intentos, llm_base_url)
                    response = await client.post(
                        f"{llm_base_url}/v1/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                response.raise_for_status()
                contenido = response.json()["choices"][0]["message"]["content"]
                resultado_ok = True
                _registrar_exito()
                break
            except (httpx.HTTPError, httpx.TimeoutException) as he:
                if intento == max_intentos:
                    logger.error("Error definitivo de comunicación con IA tras %d intentos: %s", max_intentos, he)
                    raise he
                espera = 2 ** intento
                logger.warning("Intento %d/%d fallido para conectar con IA: %s. Reintentando en %ds...", intento, max_intentos, he, espera)
                await asyncio.sleep(espera)
        
        # Remover bloques de markdown si existen
        contenido_limpio = contenido.strip()
        if contenido_limpio.startswith("```json"):
            contenido_limpio = contenido_limpio[7:]
        elif contenido_limpio.startswith("```"):
            contenido_limpio = contenido_limpio[3:]
        if contenido_limpio.endswith("```"):
            contenido_limpio = contenido_limpio[:-3]
        
        contenido_limpio = contenido_limpio.strip()
            
        # Parseo JSON resiliente (las IA a veces devuelven llaves extra '}' al final)
        resultado_ia = None
        while contenido_limpio:
            try:
                resultado_ia = json.loads(contenido_limpio)
                break
            except json.JSONDecodeError as e:
                if "Extra data" in str(e):
                    # Quitar el último caracter (usualmente una llave o salto de línea extra) y reintentar
                    contenido_limpio = contenido_limpio[:-1].strip()
                else:
                    logger.error(f"Fallo crítico al parsear JSON.\nError: {e}\nContenido:\n{contenido_limpio}")
                    raise e
                    
        if not resultado_ia:
            raise ValueError("No se pudo extraer ningún objeto JSON válido de la IA.")
            
        campos_res = resultado_ia.get("campos", {})

        # Mapear respuesta de IA al formato interno con confianza
        todos_ok = True
        for campo in campos_fallidos:
            campo_info = campos_res.get(campo, {})
            presente = campo_info.get("presente", False)
            confianza = float(campo_info.get("confianza", 0.0))
            if not presente or confianza < 0.7:
                todos_ok = False

        resultado_retorno = {
            "aprobado": todos_ok,
            "metodo": "IA_INNTI",
            "campos": campos_res,
            "explicacion": resultado_ia.get("explicacion_general", ""),
        }

        # Guardar en caché antes de retornar
        _cache_resultados_ia[hash_val] = resultado_retorno
        return resultado_retorno

    except httpx.HTTPError as he:
        logger.error("HTTP Error conectando a IA: %s", he)
        _registrar_fallo()
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

