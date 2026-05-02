"""Nivel 1: Validación heurística local de datos en texto del PDF."""

import logging
import re

from config import get_config

logger = logging.getLogger(__name__)

# Configuraciones leídas de settings.yaml o valores por defecto
_config = get_config("verificacion_grafica", {})
CAMPOS_CRITICOS = _config.get("campos_criticos", [
    "denominacion",
    "nit_emisor",
    "razon_social_emisor",
    "nit_adquiriente",
    "numero_factura",
    "valor_total",
    "cufe",
])

CAMPOS_DESEABLES = _config.get("campos_deseables", [
    "razon_social_adquiriente",
    "valor_iva",
    "numero_resolucion",
])


def normalizar_texto(texto: str) -> str:
    """Normaliza texto para comparación: mayúsculas, sin puntos de miles."""
    limpio = texto.upper().strip()
    # Remover separadores de miles comunes en Colombia
    limpio = limpio.replace(".", "").replace(",", "")
    return limpio


def normalizar_moneda(valor: str) -> str:
    """Normaliza un valor monetario para búsqueda flexible."""
    # "1500250.00" → "1500250"
    limpio = valor.replace(".", "").replace(",", "")
    # Remover decimales .00
    if limpio.endswith("00") and len(limpio) > 2:
        limpio = limpio[:-2]
    return limpio


def buscar_campo_en_texto(valor: str, texto_normalizado: str) -> bool:
    """Busca un valor dentro del texto normalizado del PDF."""
    valor_norm = normalizar_texto(valor)
    return valor_norm in texto_normalizado


def validar_datos_en_texto(
    datos_factura: dict, texto_pdf: str
) -> dict:
    """Valida que los datos procesados existan en el texto del PDF.

    Args:
        datos_factura: Diccionario con los datos extraídos del XML.
        texto_pdf: Texto completo extraído del PDF.

    Returns:
        Diccionario con resultado por campo y veredicto global.
    """
    texto_norm = normalizar_texto(texto_pdf)
    resultados = {}

    for campo in CAMPOS_CRITICOS + CAMPOS_DESEABLES:
        valor = datos_factura.get(campo)
        if not valor:
            resultados[campo] = {"encontrado": False, "motivo": "No proporcionado en XML"}
            continue

        # Monedas necesitan normalización especial
        if campo in ("valor_total", "valor_iva"):
            encontrado = normalizar_moneda(str(valor)) in texto_norm.replace(" ", "")
        else:
            encontrado = buscar_campo_en_texto(str(valor), texto_norm)

        resultados[campo] = {"encontrado": encontrado}

    criticos_ok = all(
        r["encontrado"]
        for campo, r in resultados.items()
        if campo in CAMPOS_CRITICOS and datos_factura.get(campo)
    )

    return {
        "aprobado": criticos_ok,
        "metodo": "LOCAL_PYMUPDF",
        "campos": resultados,
    }
