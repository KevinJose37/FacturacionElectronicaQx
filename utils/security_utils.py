"""Utilidades de seguridad para validación de archivos.

Incluye verificación de integridad de ZIP, validación de identidad
(magic numbers) e integración con el daemon de ClamAV para escaneo de malware.
"""

import logging
import zipfile
from pathlib import Path

import magic
import pyclamd
from config import load_yaml_config

logger = logging.getLogger(__name__)

_SETTINGS = load_yaml_config('settings.yaml')
_SECURITY_CFG = _SETTINGS.get('security', {})

class ClamAVError(Exception):
    """Excepción lanzada cuando el servicio ClamAV no está disponible."""
    pass

def get_clamav_client() -> pyclamd.ClamdNetworkSocket:
    """Establece conexión con el daemon de ClamAV.

    Returns:
        Cliente pyclamd configurado.
    
    Raises:
        ClamAVError: Si no se puede conectar al servicio.
    """
    host = _SECURITY_CFG.get('clamav_host', 'clamav')
    port = _SECURITY_CFG.get('clamav_port', 3310)
    timeout = _SECURITY_CFG.get('clamav_timeout', 10)

    try:
        cd = pyclamd.ClamdNetworkSocket(host=host, port=port, timeout=timeout)
        if cd.ping():
            return cd
        raise ClamAVError("Ping fallido a ClamAV")
    except Exception as e:
        logger.error('No se pudo conectar a ClamAV en %s:%s: %s', host, port, e)
        raise ClamAVError(f"Servicio ClamAV no alcanzable en {host}:{port}") from e

def validar_integridad_zip(ruta_zip: Path) -> bool:
    """Verifica si un archivo ZIP es válido y no está corrupto.

    Args:
        ruta_zip: Ruta al archivo a validar.

    Returns:
        True si el archivo es un ZIP íntegro, False de lo contrario.
    """
    es_valido = False
    
    if zipfile.is_zipfile(ruta_zip):
        try:
            with zipfile.ZipFile(ruta_zip, 'r') as zf:
                bad_file = zf.testzip()
                es_valido = bad_file is None
        except Exception:
            es_valido = False
    
    return es_valido

def escanear_con_clamav(ruta: Path) -> tuple:
    """Escanea un archivo en busca de virus usando ClamAV.

    Args:
        ruta: Ruta al archivo a escanear.

    Returns:
        Tupla (es_seguro, mensaje). Si es_seguro es False, el mensaje
        contiene el nombre del virus detectado o el error.
    
    Raises:
        ClamAVError: Si el servicio no está disponible.
    """
    cd = get_clamav_client()
    
    try:
        with open(ruta, 'rb') as f:
            resultado_scan = cd.scan_stream(f)
        
        if resultado_scan is None:
            return True, 'Limpio'
        else:
            virus_info = list(resultado_scan.values())[0][1]
            mensaje = f'Virus detectado: {virus_info}'
            return False, mensaje
    except ClamAVError:
        raise
    except Exception as e:
        logger.error('Error durante escaneo ClamAV para %s: %s', ruta.name, e)
        raise ClamAVError(f"Error inesperado en escaneo: {str(e)}") from e

def validar_identidad_archivo(ruta: Path, extension_esperada: str) -> bool:
    """Valida la identidad del archivo usando Magic Numbers (MIME types).

    Args:
        ruta: Ruta al archivo físico.
        extension_esperada: Extensión esperada (ej: '.pdf').

    Returns:
        True si el MIME type coincide con la extensión, False de lo contrario.
    """
    # Mapeo de extensiones permitidas a sus MIME types reales
    mime_permitidos = {
        '.zip': ['application/zip', 'application/x-zip-compressed'],
        '.pdf': ['application/pdf'],
        '.xml': ['application/xml', 'text/xml']
    }
    
    coincide = False
    try:
        # Detectar el MIME type real basado en el contenido del archivo
        tipo_real = magic.from_file(str(ruta.absolute()), mime=True)
        
        mimes_validos = mime_permitidos.get(extension_esperada.lower(), [])
        if tipo_real in mimes_validos:
            coincide = True
        else:
            logger.warning(
                "Falsificación detectada: %s dice ser %s pero es %s",
                ruta.name, extension_esperada, tipo_real
            )
    except Exception as e:
        logger.error("Error al validar Magic Numbers para %s: %s", ruta.name, e)
        
    return coincide
