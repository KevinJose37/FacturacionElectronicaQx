"""Lógica central para el procesamiento seguro de facturas post-descarga.

Coordina la validación de seguridad (corrupción y magic numbers),
la extracción del ZIP y la carga de los archivos válidos a S3.
La configuración de extensiones y rutas S3 se lee de ``config/settings.yaml``.
"""

import logging
import tempfile
import zipfile
from pathlib import Path

from config import load_yaml_config
from metadata.processor_metadata import MensajesProcessor
from utils.s3_utils import subir_archivo_s3
from utils.security_utils import validar_identidad_archivo, validar_integridad_zip

logger = logging.getLogger(__name__)

_settings = load_yaml_config('settings.yaml')
_processor_cfg = _settings.get('processor', {})
_EXTENSIONES_PERMITIDAS = _processor_cfg.get('extensiones_permitidas', ['.xml', '.pdf'])
_S3_PREFIJO_ZIP = _processor_cfg.get('s3_prefijo_zip', 'facturas')
_S3_PREFIJO_EXTRAIDOS = _processor_cfg.get('s3_prefijo_extraidos', 'facturas_descomprimidas')
_CABECERA_BYTES = int(_processor_cfg.get('cabecera_bytes', 100))


def _leer_cabecera(ruta: Path) -> bytes:
    """Lee los primeros bytes de un archivo para validación de firma.

    Args:
        ruta: Ruta absoluta al archivo a leer.
    """
    with open(ruta, 'rb') as f:
        cabecera = f.read(_CABECERA_BYTES)
    return cabecera


def _validar_zip(ruta_zip: Path) -> bool:
    """Valida que el archivo sea un ZIP legítimo y no esté corrupto.

    Ejecuta dos validaciones secuenciales: firma (magic number) e integridad.

    Args:
        ruta_zip: Ruta al archivo ZIP a validar.
    """
    cabecera = _leer_cabecera(ruta_zip)

    if not validar_identidad_archivo(cabecera, '.zip'):
        logger.error(MensajesProcessor.firma_invalida)
        resultado = False
    elif not validar_integridad_zip(ruta_zip):
        logger.error(MensajesProcessor.zip_corrupto)
        resultado = False
    else:
        resultado = True
    return resultado


def _extraer_archivos(ruta_zip: Path, destino: Path) -> list:
    """Extrae el contenido del ZIP a un directorio destino.

    Args:
        ruta_zip: Ruta al archivo ZIP.
        destino: Directorio donde extraer los archivos.

    Returns:
        Lista de rutas a los archivos extraídos.
    """
    with zipfile.ZipFile(ruta_zip, 'r') as zf:
        zf.extractall(path=destino)
    logger.info(MensajesProcessor.zip_extraido, destino)

    archivos = [p for p in destino.iterdir() if p.is_file()]
    return archivos


def _filtrar_y_validar(archivos: list) -> tuple:
    """Filtra archivos por extensión y valida su identidad (magic number).

    Args:
        archivos: Lista de rutas a archivos extraídos.

    Returns:
        Tupla (archivos_validos, malware_detectado).
    """
    validos = []
    malware_detectado = False

    for archivo in archivos:
        extension = archivo.suffix.lower()

        if extension not in _EXTENSIONES_PERMITIDAS:
            logger.info(MensajesProcessor.archivo_omitido, archivo.name)
            continue

        cabecera = _leer_cabecera(archivo)

        if not validar_identidad_archivo(cabecera, extension):
            logger.error(MensajesProcessor.identidad_fallida, archivo.name)
            malware_detectado = True
            break

        logger.info(MensajesProcessor.identidad_exitosa, archivo.name)
        validos.append(archivo)

    resultado = (validos, malware_detectado)
    return resultado


def _subir_a_s3(ruta_zip: Path, archivos_extraidos: list) -> bool:
    """Sube el ZIP original y los archivos extraídos a S3.

    Args:
        ruta_zip: Ruta al archivo ZIP original.
        archivos_extraidos: Lista de rutas a los archivos válidos extraídos.
    """
    todas_exitosas = True

    destino_zip = f'{_S3_PREFIJO_ZIP}/{ruta_zip.name}'
    if not subir_archivo_s3(ruta_zip, destino_zip):
        todas_exitosas = False

    for archivo in archivos_extraidos:
        destino = f'{_S3_PREFIJO_EXTRAIDOS}/{ruta_zip.stem}/{archivo.name}'
        if not subir_archivo_s3(archivo, destino):
            todas_exitosas = False

    return todas_exitosas


def procesar_y_subir_factura(ruta_zip: Path | str) -> bool:
    """Procesa un archivo ZIP de factura, lo valida y lo sube a S3.

    Pipeline completo:
    1. Verifica que el archivo exista.
    2. Valida firma ZIP y su integridad.
    3. Extrae a directorio temporal.
    4. Filtra por extensiones permitidas y valida identidad de cada archivo.
    5. Sube el ZIP original y los archivos válidos a S3.

    Args:
        ruta_zip: Ruta al archivo ZIP a procesar.
    """
    ruta_zip = Path(ruta_zip)
    es_exitoso = False

    if not ruta_zip.exists():
        logger.error(MensajesProcessor.zip_no_existe, ruta_zip)
        return es_exitoso

    if not _validar_zip(ruta_zip):
        return es_exitoso

    try:
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            archivos = _extraer_archivos(ruta_zip, temp_dir)
            validos, malware_detectado = _filtrar_y_validar(archivos)

            if malware_detectado:
                es_exitoso = False
            elif not validos:
                logger.warning(MensajesProcessor.sin_archivos_procesables)
            else:
                es_exitoso = _subir_a_s3(ruta_zip, validos)
    except Exception as e:
        logger.error(MensajesProcessor.error_procesamiento, ruta_zip, e)

    return es_exitoso
