"""Utilidades de seguridad para validación de archivos.

Provee mecanismos ligeros y nativos para verificar la integridad
y la verdadera identidad de los archivos mediante 'magic numbers',
previniendo la ejecución de malware básico disfrazado.
"""

import logging
import zipfile
import hashlib
import clamd
from pathlib import Path
from config import get_antivirus_config
from pathlib import Path

logger = logging.getLogger(__name__)

# Diccionario de firmas (magic numbers) esperadas
MAGIC_NUMBERS = {
    '.pdf': b'%PDF-',
    '.zip': b'PK\x03\x04',
}


def validar_integridad_zip(ruta_zip: Path | str) -> bool:
    """Verifica si un archivo ZIP está corrupto.

    Utiliza la herramienta nativa de testzip() para leer y calcular el CRC
    de cada archivo interno.

    Args:
        ruta_zip: Ruta al archivo ZIP.

    Returns:
        True si es válido y no está corrupto, 
        False en caso contrario.

    """
    ruta_zip = Path(ruta_zip)
    es_valido = False

    if not ruta_zip.exists() or not ruta_zip.is_file():
        logger.error(f"El archivo ZIP no existe: {ruta_zip}")
    else:
        try:
            with zipfile.ZipFile(ruta_zip, 'r') as zf:
                corrupt_file = zf.testzip()
                if corrupt_file:
                    logger.error(f"El archivo ZIP contiene un elemento corrupto: {corrupt_file}")
                else:
                    es_valido = True
        except zipfile.BadZipFile:
            logger.error(f"El archivo {ruta_zip} no es un ZIP válido.")
        except Exception as e:
            logger.error(f"Error inesperado al validar ZIP {ruta_zip}: {e}")

    return es_valido


def validar_identidad_archivo(contenido: bytes, extension_esperada: str) -> bool:
    """Valida la identidad del archivo basada en sus primeros bytes (magic numbers).

    Previene que un archivo .exe u otro tipo de ejecutable sea procesado
    simplemente porque fue renombrado a .pdf o .xml.

    Args:
        contenido: Los primeros bytes del archivo (se recomienda leer al menos los primeros 100 bytes).
        extension_esperada: La extensión esperada, por ejemplo '.pdf' o '.xml'.

    Returns:
        True si los magic numbers coinciden, 
        False si es sospechoso.

    """
    extension = extension_esperada.lower()
    es_valido = True

    if extension == '.xml':
        # Los XML pueden tener un BOM o espacios, pero el primer carácter real suele ser '<'
        # Los ejecutables (PE, ELF) empiezan por 'MZ' o '\x7fELF', no con '<'
        contenido_limpio = contenido.lstrip()
        if not contenido_limpio.startswith(b'<'):
            logger.warning("El archivo no parece ser un XML válido (no empieza con '<').")
            es_valido = False
    else:
        firma_esperada = MAGIC_NUMBERS.get(extension)
        if not firma_esperada:
            # Si no tenemos firma para esa extensión, somos permisivos o podríamos bloquear
            logger.warning(f"No hay firma de validación para la extensión {extension}.")
        elif not contenido.startswith(firma_esperada):
            logger.error(f"El archivo no coincide con la firma esperada para {extension}.")
            es_valido = False

    return es_valido


def calcular_hashes_archivo(ruta_archivo: Path) -> dict:
    """Calcula los hashes MD5 y SHA256 de un archivo.

    Args:
        ruta_archivo: Ruta al archivo.

    Returns:
        Diccionario con 'md5' y 'sha256'.
    """
    md5_hash = hashlib.md5()
    sha256_hash = hashlib.sha256()

    with open(ruta_archivo, "rb") as f:
        # Leer en bloques de 4KB para eficiencia
        for byte_block in iter(lambda: f.read(4096), b""):
            md5_hash.update(byte_block)
            sha256_hash.update(byte_block)

    return {"md5": md5_hash.hexdigest(), "sha256": sha256_hash.hexdigest()}


def escanear_con_clamav(ruta_archivo: Path) -> dict:
    """Escanea un archivo en busca de malware usando ClamAV local.

    Args:
        ruta_archivo: Ruta al archivo a escanear.

    Returns:
        Diccionario con los resultados del escaneo.
    """
    config = get_antivirus_config()
    resultado_final = {
        "malware_detectado": False,
        "nombre_virus": None,
        "version_motor": "ClamAV 1.0 (Local)",
        "detalles": None,
    }

    try:
        # Intentar conectar con el socket de red del contenedor
        cd = clamd.ClamdNetworkSocket(host=config["host"], port=config["port"])

        # Realizar el escaneo (instream envía el archivo por el socket)
        # Esto es necesario si el contenedor no tiene acceso al sistema de archivos local
        with open(ruta_archivo, "rb") as f:
            resultado = cd.instream(f)

        # Respuesta de clamd: {'stream': ('status', 'virus_name')}
        if resultado and "stream" in resultado:
            status, virus_name = resultado["stream"]
            if status == "FOUND":
                resultado_final["malware_detectado"] = True
                resultado_final["nombre_virus"] = virus_name
                resultado_final["detalles"] = f"Virus detectado: {virus_name}"
            else:
                resultado_final["detalles"] = "Archivo limpio"

        # Obtener versión del motor
        resultado_final["version_motor"] = cd.version()

    except Exception as e:
        logger.error(f"Error al escanear con ClamAV: {e}")
        resultado_final["detalles"] = f"Error de conexión/escaneo: {str(e)}"

    return resultado_final
