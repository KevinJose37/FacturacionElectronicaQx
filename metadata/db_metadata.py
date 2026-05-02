"""Metadatos del módulo de base de datos.

Mensajes de error y textos del pool de conexiones y cache.
"""

class IdEstadoProceso:
    """Estados de proceso para ingesta de facturas."""

    pendiente = 1
    """Estado pendiente de procesamiento."""

    en_proceso = 2
    """Estado en proceso de ingesta."""

    procesado = 3
    """Estado procesado de ingesta."""

    error = 4
    """Estado de error en el procesamiento."""

    fallido = 5
    """Estado de fallo definitivo (agotó reintentos)."""


class IdTipoArchivo:
    """Tipos de archivos para ingesta de facturas."""

    zip = 1
    """Archivo ZIP para ingesta de facturas."""

    xml = 2
    """Archivo XML para ingesta de facturas."""

    pdf = 3
    """Archivo PDF para ingesta de facturas."""


class IdTipoProceso:
    """Tipos de procesos de ingesta de facturas.

    Corresponden a la tabla FACTURACION.TIPO_PROCESO.
    """

    escaneo_malware = 1
    """Verificación de archivos contra virus y malware."""

    descarga_almacenamiento = 2
    """Descarga y almacenamiento del archivo en S3."""

    validacion_contenido_zip = 3
    """Verificación de que el ZIP contiene XML y PDF completos."""

    extraccion_zip = 4
    """Extracción de archivos del ZIP."""

    registro_adjuntos = 5
    """Registro de adjuntos en la base de datos."""

    verificacion_grafica = 6
    """Verificación de representación gráfica PDF vs XML."""


class MensajesDB:
    """Mensajes de error y log del módulo de base de datos."""

    pool_no_inicializado = 'El pool de conexiones no ha sido inicializado. Llama a init_pool() primero.'
    """Error cuando se intenta obtener el pool antes de inicializarlo. Usado en connection.py."""

    pool_inicializado = 'Pool de conexiones async inicializado (%s:%s/%s)'
    """Mensaje de log al inicializar el pool. Usado en connection.py."""

    pool_cerrado = 'Pool de conexiones async cerrado.'
    """Mensaje de log al cerrar el pool. Usado en connection.py."""

    cache_set = 'Cache SET: %s (ttl=%ds)'
    """Mensaje de log al guardar una entrada en cache. Usado en cache.py."""

    cache_cleared = 'Cache CLEARED (all keys)'
    """Mensaje de log al limpiar todo el cache. Usado en cache.py."""

    cache_invalidated = 'Cache INVALIDATED: %s'
    """Mensaje de log al invalidar una clave específica. Usado en cache.py."""
