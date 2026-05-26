"""Extracción de texto y renderizado de PDFs con PyMuPDF."""

import fitz  # PyMuPDF
import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def extraer_texto_pdf(ruta_pdf: str | Path) -> tuple[str, bool]:
    """Extrae el texto completo del PDF.

    Args:
        ruta_pdf: Ruta al archivo PDF.

    Returns:
        Tupla (texto_completo, es_nativo).
        es_nativo=True si el PDF tiene capa de texto útil.
    """
    doc = fitz.open(str(ruta_pdf))
    texto_paginas = []

    for pagina in doc:
        texto_paginas.append(pagina.get_text("text"))

    doc.close()

    texto_completo = "\n".join(texto_paginas)
    # Si el texto tiene menos de 50 caracteres, probablemente es imagen
    es_nativo = len(texto_completo.strip()) > 50

    return texto_completo, es_nativo


def renderizar_pdf_a_base64(ruta_pdf: str | Path, pagina_idx: int = 0) -> str:
    """Convierte una página del PDF a imagen JPEG en base64.

    Solo se usa cuando se necesita enviar a la IA (Nivel 2).

    Args:
        ruta_pdf: Ruta al archivo PDF.
        pagina_idx: Índice de la página a renderizar.

    Returns:
        String base64 de la imagen JPEG.
    """
    doc = fitz.open(str(ruta_pdf))
    pagina = doc.load_page(pagina_idx)
    # Zoom x2 para mejor resolución
    pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2))
    img_bytes = pix.tobytes("jpg", jpg_quality=80)
    doc.close()

    return base64.b64encode(img_bytes).decode("utf-8")


def renderizar_pdf_a_base64_paginas(ruta_pdf: str | Path) -> list[str]:
    """Renderiza páginas seleccionadas del PDF a imágenes JPEG en base64.

    Si tiene <= 2 páginas, renderiza todas.
    Si tiene > 2 páginas, renderiza la primera (0) y la última (len - 1).

    Args:
        ruta_pdf: Ruta al archivo PDF.

    Returns:
        Lista de strings base64 en formato JPEG.
    """
    doc = fitz.open(str(ruta_pdf))
    num_paginas = len(doc)

    if num_paginas <= 0:
        doc.close()
        return []

    if num_paginas <= 2:
        indices = list(range(num_paginas))
    else:
        indices = [0, num_paginas - 1]

    imagenes_base64 = []
    for idx in indices:
        pagina = doc.load_page(idx)
        pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("jpg", jpg_quality=80)
        imagenes_base64.append(base64.b64encode(img_bytes).decode("utf-8"))

    doc.close()
    return imagenes_base64
