"""Validador de adjuntos para facturación electrónica.

Verifica que el archivo ZIP contenga al menos un XML y un PDF válidos,
y realiza la extracción temporal para validaciones posteriores.
"""

import logging
import zipfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Resultado de la validación de un archivo ZIP."""
    es_valido: bool
    archivos_encontrados: List[str] = field(default_factory=list)
    motivo_error: Optional[str] = None
    xml_path: Optional[Path] = None
    pdf_path: Optional[Path] = None


class AttachmentValidator:
    """Valida y extrae contenido de adjuntos ZIP."""

    def __init__(self, temp_dir: str = "temp"):
        """Inicializa el validador.

        Args:
            temp_dir: Directorio para extracción temporal.
        """
        self.temp_root = Path(temp_dir)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def validar_zip(self, ruta_zip: Path) -> ValidationResult:
        """Valida que el ZIP contenga un XML y un PDF.

        Args:
            ruta_zip: Path al archivo ZIP.

        Returns:
            ValidationResult con el estado y rutas de archivos extraídos.
        """
        if not zipfile.is_zipfile(ruta_zip):
            return ValidationResult(es_valido=False, motivo_error="Archivo no es un ZIP válido")

        archivos_en_zip = []
        xml_file = None
        pdf_file = None

        try:
            with zipfile.ZipFile(ruta_zip, 'r') as z:
                archivos_en_zip = z.namelist()
                
                # Buscar XML y PDF (ignorando mayúsculas/minúsculas y subcarpetas si las hay)
                for f in archivos_en_zip:
                    name_lower = f.lower()
                    if name_lower.endswith(".xml") and not xml_file:
                        xml_file = f
                    elif name_lower.endswith(".pdf") and not pdf_file:
                        pdf_file = f

                if not xml_file or not pdf_file:
                    motivo = "Falta " + ("XML" if not xml_file else "") + (" y " if not xml_file and not pdf_file else "") + ("PDF" if not pdf_file else "")
                    return ValidationResult(es_valido=False, archivos_encontrados=archivos_en_zip, motivo_error=motivo)

                # Extraer a carpeta temporal única para este ZIP
                extract_dir = self.temp_root / ruta_zip.stem
                extract_dir.mkdir(parents=True, exist_ok=True)
                
                z.extract(xml_file, extract_dir)
                z.extract(pdf_file, extract_dir)
                
                return ValidationResult(
                    es_valido=True,
                    archivos_encontrados=archivos_en_zip,
                    xml_path=extract_dir / xml_file,
                    pdf_path=extract_dir / pdf_file
                )

        except Exception as e:
            logger.error(f"Error procesando ZIP {ruta_zip}: {e}")
            return ValidationResult(es_valido=False, motivo_error=f"Error interno: {str(e)}")

    def limpiar_temp(self):
        """Elimina todos los archivos del directorio temporal."""
        if self.temp_root.exists():
            for item in self.temp_root.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            logger.debug("Directorio temporal limpiado")
