"""Lógica central para el procesamiento seguro de facturas post-descarga.

Coordina la validación de seguridad (corrupción y magic numbers),
la extracción del ZIP y la carga de los archivos válidos a S3.
"""

import logging
import tempfile
import zipfile
from pathlib import Path

from utils.security_utils import validar_identidad_archivo, validar_integridad_zip
from utils.s3_utils import subir_archivo_s3

logger = logging.getLogger(__name__)


def procesar_y_subir_factura(ruta_zip: Path | str) -> bool:
    """Procesa un archivo ZIP de factura, lo valida y lo sube a S3.

    1. Valida identidad e integridad del ZIP.
    2. Extrae contenido a un entorno temporal.
    3. Identifica PDF y XML, y valida sus firmas (magic numbers) antes de procesarlos.
    4. Sube los archivos originales a S3.

    Args:
        ruta_zip: Ruta al archivo ZIP descargado localmente.

    Returns:
        True si el proceso completo fue exitoso, False en caso de error o detección de malware.

    """
    ruta_zip = Path(ruta_zip)
    es_exitoso = False

    if not ruta_zip.exists():
        logger.error(f"El archivo ZIP no existe: {ruta_zip}")
    else:
        # 1. Validar ZIP
        with open(ruta_zip, 'rb') as f:
            cabecera = f.read(100)
            
        if not validar_identidad_archivo(cabecera, '.zip'):
            logger.error("El archivo proporcionado no tiene la firma de un ZIP.")
        elif not validar_integridad_zip(ruta_zip):
            logger.error("El archivo ZIP está corrupto o es inválido.")
        else:
            archivos_extraidos = []

            # 2. Extraer a directorio temporal seguro
            try:
                with tempfile.TemporaryDirectory() as temp_dir_str:
                    temp_dir = Path(temp_dir_str)
                    
                    with zipfile.ZipFile(ruta_zip, 'r') as zf:
                        zf.extractall(path=temp_dir)
                        logger.info(f"ZIP extraído temporalmente en {temp_dir}")
                    
                    # 3. Validar identidad de PDF y XML
                    archivos_procesables = [p for p in temp_dir.iterdir() if p.is_file()]
                    malware_detectado = False
                    
                    for archivo in archivos_procesables:
                        extension = archivo.suffix.lower()
                        
                        # Solo procesamos XML y PDF, ignoramos el resto (prevención)
                        if extension not in ['.xml', '.pdf']:
                            logger.info(f"Se omite archivo no soportado: {archivo.name}")
                            continue

                        # Leer cabecera para validación de seguridad
                        with open(archivo, 'rb') as f:
                            cabecera_archivo = f.read(100)

                        if not validar_identidad_archivo(cabecera_archivo, extension):
                            logger.error(f"Archivo {archivo.name} falló la validación de identidad. Posible malware.")
                            malware_detectado = True
                            break

                        logger.info(f"Validación de identidad exitosa para {archivo.name}")
                        archivos_extraidos.append(archivo)

                    if not malware_detectado:
                        if not archivos_extraidos:
                            logger.warning("El ZIP no contenía archivos XML o PDF procesables.")
                        else:
                            # 4. Subir a S3
                            todas_exitosas = True
                            
                            # Subir el ZIP original como respaldo
                            destino_s3_zip = f"facturas/{ruta_zip.name}"
                            if not subir_archivo_s3(ruta_zip, destino_s3_zip):
                                todas_exitosas = False

                            # Subir archivos internos
                            for archivo in archivos_extraidos:
                                destino_s3 = f"facturas_descomprimidas/{ruta_zip.stem}/{archivo.name}"
                                if not subir_archivo_s3(archivo, destino_s3):
                                    todas_exitosas = False

                            es_exitoso = todas_exitosas

            except Exception as e:
                logger.error(f"Error procesando el ZIP {ruta_zip}: {e}")

    return es_exitoso
