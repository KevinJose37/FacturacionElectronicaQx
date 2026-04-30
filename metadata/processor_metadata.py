"""Metadatos del procesador de facturas.

Mensajes de log y error para el pipeline de procesamiento de archivos ZIP.
"""


class MensajesProcessor:
    """Mensajes de log para el procesamiento de facturas ZIP."""

    zip_no_existe = 'El archivo ZIP no existe: %s'
    """Error cuando la ruta del ZIP apunta a un archivo inexistente. Usado en processor.py."""

    firma_invalida = 'El archivo proporcionado no tiene la firma de un ZIP.'
    """Error cuando el magic number del archivo no corresponde a ZIP. Usado en processor.py."""

    zip_corrupto = 'El archivo ZIP está corrupto o es inválido.'
    """Error cuando el ZIP falla la validación de integridad. Usado en processor.py."""

    zip_extraido = 'ZIP extraído temporalmente en %s'
    """Info cuando el ZIP se extrae exitosamente a un directorio temporal. Usado en processor.py."""

    archivo_omitido = 'Se omite archivo no soportado: %s'
    """Info cuando un archivo dentro del ZIP tiene extensión no permitida. Usado en processor.py."""

    identidad_fallida = 'Archivo %s falló la validación de identidad. Posible malware.'
    """Error cuando un archivo extraído no pasa la validación de magic number. Usado en processor.py."""

    identidad_exitosa = 'Validación de identidad exitosa para %s'
    """Info cuando un archivo pasa la validación de magic number. Usado en processor.py."""

    sin_archivos_procesables = 'El ZIP no contenía archivos XML o PDF procesables.'
    """Warning cuando el ZIP no contiene archivos con extensiones permitidas. Usado en processor.py."""

    error_procesamiento = 'Error procesando el ZIP %s: %s'
    """Error genérico cuando ocurre una excepción durante el procesamiento. Usado en processor.py."""
