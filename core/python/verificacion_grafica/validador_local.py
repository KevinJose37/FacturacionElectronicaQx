"""Nivel 1: Validación heurística local de datos en texto del PDF."""

import logging
import re

from config import load_yaml_config

logger = logging.getLogger(__name__)

# Configuraciones leídas de settings.yaml o valores por defecto
_settings = load_yaml_config("settings.yaml")
_config = _settings.get("verificacion_grafica", {})
CAMPOS_CRITICOS = _config.get("campos_criticos", [
    "denominacion",
    "nit_emisor",
    "razon_social_emisor",
    "nit_adquiriente",
    "numero_factura",
    "valor_total",
    "cufe",
    "fecha_hora_generacion",
])

CAMPOS_DESEABLES = _config.get("campos_deseables", [
    "razon_social_adquiriente",
    "iva",
    "resolucion_dian",
    "forma_pago",
    "calidad_tributaria",
    "informacion_software",
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


def comparar_nit(nit: str, texto_pdf: str) -> bool:
    """Compara un NIT de forma robusta con el texto del PDF.

    Soporta presencia/ausencia de puntos, guiones y dígitos de verificación (DV).
    """
    digitos_nit = "".join(c for c in nit if c.isdigit())
    if not digitos_nit:
        return False

    # Variaciones: NIT completo (con DV) y sin el último dígito (asumiendo que es DV)
    variaciones = [digitos_nit]
    if len(digitos_nit) == 10:  # Ej. 9015762003 -> buscar 901576200
        variaciones.append(digitos_nit[:-1])

    # Texto limpio del PDF removiendo puntuación para comparación directa
    texto_limpio_pdf = re.sub(r'[\.\-\s\/]', '', texto_pdf)

    for var in variaciones:
        # 1. Búsqueda directa sin puntuación en el PDF
        if var in texto_limpio_pdf:
            return True

        # 2. Búsqueda con expresión regular tolerando espacios o puntos intermedios
        regex_pattern = r"[\s\.\-\/]*".join(var)
        if re.search(regex_pattern, texto_pdf):
            return True

    return False


def comparar_fecha(xml_fecha: str, texto_norm: str) -> bool:
    """Compara una fecha en formato XML con múltiples representaciones en español."""
    fecha_limpia = xml_fecha.split("T")[0].split(" ")[0].strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", fecha_limpia)
    if not match:
        return normalizar_texto(xml_fecha) in texto_norm

    yyyy, mm, dd = match.groups()
    yyyy_short = yyyy[2:]
    mm_int = int(mm)
    dd_int = int(dd)

    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    mes_nombre = meses[mm_int - 1]
    mes_corto = mes_nombre[:3]

    variaciones = [
        f"{yyyy}-{mm}-{dd}",
        f"{dd}/{mm}/{yyyy}",
        f"{dd}-{mm}-{yyyy}",
        f"{dd}/{mm}/{yyyy_short}",
        f"{dd}-{mm}-{yyyy_short}",
        f"{dd_int}/{mm_int}/{yyyy}",
        f"{dd_int}/{mm_int}/{yyyy_short}",
        f"{dd_int} de {mes_nombre} de {yyyy}",
        f"{dd_int} {mes_nombre} {yyyy}",
        f"{mes_nombre} {dd_int} {yyyy}",
        f"{mes_corto} {dd_int} {yyyy}",
    ]

    for var in variaciones:
        var_norm = normalizar_texto(var)
        if var_norm in texto_norm:
            return True
    return False


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

        # Validaciones de campos con lógica especializada
        if campo in ("valor_total", "iva"):
            encontrado = normalizar_moneda(str(valor)) in texto_norm.replace(" ", "")
        elif campo in ("nit_emisor", "nit_adquiriente"):
            encontrado = comparar_nit(str(valor), texto_pdf)
        elif campo == "fecha_hora_generacion":
            encontrado = comparar_fecha(str(valor), texto_norm)
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
