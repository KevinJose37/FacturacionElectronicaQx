"""Controlador de verificación gráfica híbrida."""

import json
import logging
from pathlib import Path
from typing import Optional

from core.python.verificacion_grafica.extractor_texto_pdf import (
    extraer_texto_pdf,
    renderizar_pdf_a_base64_paginas,
)
from core.python.verificacion_grafica.validador_local import (
    validar_datos_en_texto,
    CAMPOS_CRITICOS,
    CAMPOS_DESEABLES,
)
from core.python.verificacion_grafica.validador_ia import verificar_con_ia

logger = logging.getLogger(__name__)


def _guardar_detalle_verificacion(conn, id_factura: int, detalle: dict) -> None:
    """Persiste el resultado detallado de la verificación gráfica en la BD.

    Usa la conexión síncrona del worker (no el async pool de FastAPI).
    """
    try:
        detalle_json = json.dumps(detalle, ensure_ascii=False, default=str)
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE facturacion.factura
                   SET verificacion_grafica_detalle = %s
                   WHERE id_factura = %s""",
                [detalle_json, id_factura],
            )
    except Exception as e:
        # Column might not exist yet — log but don't fail the flow
        logger.warning("No se pudo guardar detalle de verificación gráfica: %s", e)


async def verificar_representacion_grafica(
    ruta_pdf: str | Path,
    datos_factura: dict,
    id_factura: int | None = None,
    conn=None,
) -> dict:
    """Ejecuta la verificación gráfica en cascada.

    Nivel 1: Extrae texto con PyMuPDF y busca los datos.
    Nivel 2: Si falla, renderiza a imagen y consulta IA Innti.

    Args:
        ruta_pdf: Ruta al PDF de la factura.
        datos_factura: Datos procesados del XML (ya validados).
        id_factura: ID opcional para persistir el resultado detallado.

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
            if id_factura and conn:
                _guardar_detalle_verificacion(conn, id_factura, resultado)
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
            c for c in (CAMPOS_CRITICOS + CAMPOS_DESEABLES) if datos_factura.get(c)
        ]
        resultado = None
        logger.info("PDF sin texto nativo o con error. Escalando directo a IA.")

    # ── Nivel 2: Fallback con IA ──
    try:
        imagenes_b64 = renderizar_pdf_a_base64_paginas(ruta_pdf)
        resultado_ia = await verificar_con_ia(
            imagenes_b64, datos_factura, campos_fallidos
        )

        # Merge local results (for fields that passed level 1) with IA results
        if resultado and resultado.get("campos"):
            merged_campos = {}
            for campo, info in resultado["campos"].items():
                if info.get("encontrado"):
                    merged_campos[campo] = {
                        "presente": True,
                        "confianza": 1.0,
                        "detalle": "Verificado localmente (texto extraído del PDF)",
                    }
                else:
                    # Use IA result if available, otherwise mark as failed
                    ia_campo = resultado_ia.get("campos", {}).get(campo, {})
                    merged_campos[campo] = ia_campo if ia_campo else {
                        "presente": False,
                        "confianza": 0.0,
                        "detalle": "No encontrado",
                    }
            resultado_ia["campos"] = merged_campos

        estado = "APROBADA" if resultado_ia["aprobado"] else "RECHAZADA"
        logger.info("Verificación gráfica %s (IA Innti)", estado)

        # Persist the detailed result
        if id_factura and conn:
            _guardar_detalle_verificacion(conn, id_factura, resultado_ia)

        return resultado_ia

    except Exception as e:
        logger.error("Error en verificación IA: %s", e)
        return {
            "aprobado": False,
            "metodo": "ERROR",
            "observacion": f"Fallo en ambos niveles: {str(e)}",
            "requiere_revision_humana": True,
        }

