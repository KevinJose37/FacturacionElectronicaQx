"""Validador de adjuntos para facturación electrónica.

Verifica que los archivos adjuntos contengan la información necesaria
para el procesamiento de facturas electrónicas (XML + PDF).

Soporta:
    - ZIP con XML y PDF directos
    - ZIP con ZIPs anidados (cada uno con su XML y PDF)
    - XML y PDF sueltos (sin ZIP contenedor)
"""

import logging
import re
import zipfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ParXmlPdf:
    """Un par XML+PDF que representa los archivos de una factura.

    Attributes:
        xml_path: Ruta al archivo XML extraído.
        pdf_path: Ruta al archivo PDF extraído.
        zip_origen: Ruta al ZIP del que se extrajeron (None si son sueltos).
    """
    xml_path: Path
    pdf_path: Path
    zip_origen: Optional[Path] = None


@dataclass
class ValidationResult:
    """Resultado de la validación de un archivo ZIP."""
    es_valido: bool
    archivos_encontrados: List[str] = field(default_factory=list)
    motivo_error: Optional[str] = None
    xml_path: Optional[Path] = None
    pdf_path: Optional[Path] = None


@dataclass
class ZipValidacionCompleta:
    """Resultado completo de validación de un ZIP, con soporte para ZIPs anidados.

    Attributes:
        es_valido: Si el ZIP y su contenido son válidos.
        motivo_error: Razón del error (None si es válido).
        pares: Lista de pares XML+PDF encontrados (directos o dentro de sub-ZIPs).
        archivos_encontrados: Lista de nombres de archivos en el ZIP.
        tiene_zips_anidados: Si el ZIP contiene otros ZIPs.
    """
    es_valido: bool
    motivo_error: Optional[str] = None
    pares: List[ParXmlPdf] = field(default_factory=list)
    archivos_encontrados: List[str] = field(default_factory=list)
    tiene_zips_anidados: bool = False


class AttachmentValidator:
    """Valida y extrae contenido de adjuntos ZIP."""

    # Profundidad máxima para ZIPs anidados (ZIP de ZIP de ZIP...)
    MAX_DEPTH = 5

    def __init__(self, temp_dir: str = "temp"):
        """Inicializa el validador.

        Args:
            temp_dir: Directorio para extracción temporal.
        """
        self.temp_root = Path(temp_dir)
        self.temp_root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _extraer_digitos(nombre: str) -> str:
        """Extrae la secuencia de dígitos de un nombre de archivo.

        Permite emparejar archivos como:
            ad007126073200026000002fa.xml  ↔  fv007126073200026000002fa.pdf

        La clave de emparejamiento es la concatenación de todos los dígitos.

        Args:
            nombre: Nombre del archivo (sin extensión).

        Returns:
            Cadena con todos los dígitos del nombre, o cadena vacía si no hay.
        """
        return ''.join(re.findall(r'\d+', nombre))

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

    def validar_zip_completo(self, ruta_zip: Path, _depth: int = 0) -> ZipValidacionCompleta:
        """Valida un ZIP con soporte para ZIPs anidados (multi-nivel).

        Analiza el contenido del ZIP buscando:
        1. XML+PDF directos → genera un par
        2. ZIPs internos → extrae y valida cada sub-ZIP recursivamente
        3. Mezcla de ambos

        La recursión tiene un límite de MAX_DEPTH niveles para evitar
        bucles infinitos con ZIPs malformados.

        Args:
            ruta_zip: Path al archivo ZIP.
            _depth: Nivel actual de recursión (uso interno).

        Returns:
            ZipValidacionCompleta con todos los pares encontrados.
        """
        if _depth >= self.MAX_DEPTH:
            return ZipValidacionCompleta(
                es_valido=False,
                motivo_error=f"Profundidad máxima de ZIPs anidados excedida ({self.MAX_DEPTH})"
            )

        if not zipfile.is_zipfile(ruta_zip):
            return ZipValidacionCompleta(
                es_valido=False,
                motivo_error="Archivo no es un ZIP válido"
            )

        try:
            with zipfile.ZipFile(ruta_zip, 'r') as z:
                archivos_en_zip = z.namelist()

                # Clasificar archivos por tipo
                xml_files = []
                pdf_files = []
                zip_files = []

                for f in archivos_en_zip:
                    # Ignorar directorios y archivos ocultos
                    if f.endswith('/') or f.startswith('__MACOSX'):
                        continue
                    name_lower = f.lower()
                    if name_lower.endswith(".xml"):
                        xml_files.append(f)
                    elif name_lower.endswith(".pdf"):
                        pdf_files.append(f)
                    elif name_lower.endswith(".zip"):
                        zip_files.append(f)

                pares: List[ParXmlPdf] = []
                tiene_zips_anidados = len(zip_files) > 0

                # Caso 1: El ZIP contiene XML+PDF directos
                if xml_files and pdf_files:
                    extract_dir = self.temp_root / ruta_zip.stem
                    extract_dir.mkdir(parents=True, exist_ok=True)

                    # Extraer XML y PDF
                    for xf in xml_files:
                        z.extract(xf, extract_dir)
                    for pf in pdf_files:
                        z.extract(pf, extract_dir)

                    # Emparejar XMLs y PDFs:
                    # 1° intento: por stem exacto (mismo nombre, diferente extensión)
                    # 2° intento: por dígitos internos (ej: ad0071...xml ↔ fv0071...pdf)
                    pdf_por_stem = {Path(pf).stem.lower(): pf for pf in pdf_files}
                    pdf_por_digitos = {}
                    for pf in pdf_files:
                        digitos = self._extraer_digitos(Path(pf).stem)
                        if digitos:
                            pdf_por_digitos[digitos] = pf

                    pdf_usados = set()

                    for xf in xml_files:
                        stem_xml = Path(xf).stem.lower()
                        # Intento 1: match exacto por stem
                        pdf_match = pdf_por_stem.get(stem_xml)
                        if not pdf_match:
                            # Intento 2: match por dígitos
                            digitos_xml = self._extraer_digitos(stem_xml)
                            if digitos_xml:
                                pdf_match = pdf_por_digitos.get(digitos_xml)

                        if pdf_match:
                            pares.append(ParXmlPdf(
                                xml_path=extract_dir / xf,
                                pdf_path=extract_dir / pdf_match,
                                zip_origen=ruta_zip,
                            ))
                            pdf_usados.add(Path(pdf_match).stem.lower())
                        else:
                            logger.warning(
                                "XML sin PDF correspondiente en ZIP %s: %s",
                                ruta_zip.name, xf
                            )

                    for pf in pdf_files:
                        if Path(pf).stem.lower() not in pdf_usados:
                            logger.warning(
                                "PDF sin XML correspondiente en ZIP %s: %s",
                                ruta_zip.name, pf
                            )

                # Caso 2: El ZIP contiene sub-ZIPs
                if zip_files:
                    extract_dir = self.temp_root / ruta_zip.stem
                    extract_dir.mkdir(parents=True, exist_ok=True)

                    for zf_name in zip_files:
                        z.extract(zf_name, extract_dir)
                        sub_zip_path = extract_dir / zf_name

                        # Validar recursivamente cada sub-ZIP (con control de profundidad)
                        sub_resultado = self.validar_zip_completo(sub_zip_path, _depth=_depth + 1)
                        if sub_resultado.es_valido and sub_resultado.pares:
                            # Ajustar zip_origen al sub-ZIP
                            for par in sub_resultado.pares:
                                par.zip_origen = sub_zip_path
                            pares.extend(sub_resultado.pares)
                        else:
                            logger.warning(
                                "Sub-ZIP inválido dentro de %s: %s | Motivo: %s",
                                ruta_zip.name, zf_name,
                                sub_resultado.motivo_error or "sin pares XML+PDF"
                            )

                # Evaluar resultado
                if not pares:
                    motivo_parts = []
                    if not xml_files and not zip_files:
                        motivo_parts.append("no contiene archivos XML")
                    if not pdf_files and not zip_files:
                        motivo_parts.append("no contiene archivos PDF")
                    if zip_files and not pares:
                        motivo_parts.append("ZIPs internos no contienen pares XML+PDF válidos")
                    motivo = "ZIP inválido: " + ", ".join(motivo_parts) if motivo_parts else "ZIP vacío o sin contenido de factura"

                    return ZipValidacionCompleta(
                        es_valido=False,
                        motivo_error=motivo,
                        archivos_encontrados=archivos_en_zip,
                        tiene_zips_anidados=tiene_zips_anidados,
                    )

                return ZipValidacionCompleta(
                    es_valido=True,
                    pares=pares,
                    archivos_encontrados=archivos_en_zip,
                    tiene_zips_anidados=tiene_zips_anidados,
                )

        except Exception as e:
            logger.error("Error procesando ZIP %s: %s", ruta_zip, e)
            return ZipValidacionCompleta(
                es_valido=False,
                motivo_error=f"Error interno: {str(e)}"
            )

    def agrupar_pares_sueltos(
        self,
        xmls: List[Path],
        pdfs: List[Path],
    ) -> List[ParXmlPdf]:
        """Agrupa archivos XML y PDF sueltos en pares de factura.

        Empareja por nombre de archivo (mismo stem) o por dígitos
        internos (ej: ad0071260732...xml ↔ fv0071260732...pdf).
        Los archivos sin pareja se registran como advertencia.

        Args:
            xmls: Lista de rutas a archivos XML sueltos.
            pdfs: Lista de rutas a archivos PDF sueltos.

        Returns:
            Lista de pares ParXmlPdf (sin zip_origen).
        """
        pares: List[ParXmlPdf] = []

        # Indexar PDFs por stem y por dígitos
        pdf_por_stem = {p.stem.lower(): p for p in pdfs}
        pdf_por_digitos = {}
        for p in pdfs:
            digitos = self._extraer_digitos(p.stem)
            if digitos:
                pdf_por_digitos[digitos] = p

        pdf_usados = set()

        for xml_path in xmls:
            stem = xml_path.stem.lower()
            # Intento 1: match exacto por stem
            pdf_match = pdf_por_stem.get(stem)
            if not pdf_match:
                # Intento 2: match por dígitos
                digitos = self._extraer_digitos(stem)
                if digitos:
                    pdf_match = pdf_por_digitos.get(digitos)

            if pdf_match:
                pares.append(ParXmlPdf(
                    xml_path=xml_path,
                    pdf_path=pdf_match,
                    zip_origen=None,
                ))
                pdf_usados.add(pdf_match.stem.lower())
            else:
                logger.warning("XML sin PDF correspondiente (suelto): %s", xml_path.name)

        for pdf_path in pdfs:
            if pdf_path.stem.lower() not in pdf_usados:
                logger.warning("PDF sin XML correspondiente (suelto): %s", pdf_path.name)

        return pares

    def limpiar_temp(self):
        """Elimina todos los archivos del directorio temporal."""
        if self.temp_root.exists():
            for item in self.temp_root.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
            logger.debug("Directorio temporal limpiado")
