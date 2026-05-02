"""Controlador de verificación gráfica híbrida."""

import logging
from pathlib import Path

from core.python.verificacion_grafica.extractor_texto_pdf import (
    extraer_texto_pdf,
    renderizar_pdf_a_base64,
)
from core.python.verificacion_grafica.validador_local import (
    validar_datos_en_texto,
    CAMPOS_CRITICOS,
)
from core.python.verificacion_grafica.validador_ia import verificar_con_ia

logger = logging.getLogger(__name__)


async def verificar_representacion_grafica(
    ruta_pdf: str | Path,
    datos_factura: dict,
) -> dict:
    """Ejecuta la verificación gráfica en cascada.

    Nivel 1: Extrae texto con PyMuPDF y busca los datos.
    Nivel 2: Si falla, renderiza a imagen y consulta IA Innti.

    Args:
        ruta_pdf: Ruta al PDF de la factura.
        datos_factura: Datos procesados del XML (ya validados).

    Returns:
        Diccionario con: aprobado, metodo, campos, observacion.
    """
    # ── Nivel 1: Extracción local ──
    try:
        texto_pdf, es_nativo = extraer_texto_pdf(ruta_pdf)
    except Exception as e:
        logger.error(f"Fallo al extraer texto del PDF {ruta_pdf}: {e}")
        es_nativo = False

    if es_nativo:
        resultado = validar_datos_en_texto(datos_factura, texto_pdf)

        if resultado["aprobado"]:
            logger.info("Verificación gráfica APROBADA (local)")
            return resultado

        # Identificar campos que fallaron para escalar solo esos
        campos_fallidos = [
            campo for campo, info in resultado["campos"].items()
            if not info.get("encontrado") and datos_factura.get(campo)
        ]
        logger.warning(
            "Nivel 1 falló en campos: %s. Escalando a IA.", campos_fallidos
        )
    else:
        campos_fallidos = [
            c for c in CAMPOS_CRITICOS if datos_factura.get(c)
        ]
        logger.info("PDF sin texto nativo o con error. Escalando directo a IA.")

    # ── Nivel 2: Fallback con IA ──
    try:
        imagen_b64 = renderizar_pdf_a_base64(ruta_pdf)
        resultado_ia = await verificar_con_ia(
            imagen_b64, datos_factura, campos_fallidos
        )
        estado = "APROBADA" if resultado_ia["aprobado"] else "RECHAZADA"
        logger.info("Verificación gráfica %s (IA Innti)", estado)
        return resultado_ia

    except Exception as e:
        logger.error("Error en verificación IA: %s", e)
        return {
            "aprobado": False,
            "metodo": "ERROR",
            "observacion": f"Fallo en ambos niveles: {str(e)}",
            "requiere_revision_humana": True,
        }
