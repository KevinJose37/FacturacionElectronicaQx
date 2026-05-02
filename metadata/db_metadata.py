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


class IdTipoError:
    """Tipos de error en el procesamiento de ingesta.

    Corresponden a la tabla FACTURACION.TIPO_ERROR.
    Se usan en la columna ID_ERROR de PROCESO_INGESTA.
    """

    # -- Escaneo de malware (ESCANEO_MALWARE) --
    malware_detectado = 1
    """ClamAV detectó virus o malware en el archivo."""

    extension_prohibida = 2
    """El archivo tiene una extensión peligrosa (.exe, .bat, etc.)."""

    tamano_excedido = 3
    """El archivo excede el tamaño máximo permitido."""

    # -- Validación de contenido ZIP (VALIDACION_CONTENIDO_ZIP) --
    zip_corrupto = 4
    """El archivo ZIP está corrupto o no es válido."""

    zip_sin_xml = 5
    """El ZIP no contiene archivos XML de factura."""

    zip_profundidad_excedida = 6
    """ZIPs anidados exceden la profundidad máxima permitida."""

    zip_subzip_invalido = 7
    """Un sub-ZIP dentro del ZIP principal no contiene pares válidos."""

    # -- Descarga y almacenamiento (DESCARGA_ALMACENAMIENTO) --
    fallo_descarga_adjuntos = 8
    """No se pudieron descargar los adjuntos del correo."""

    fallo_subida_s3 = 9
    """Error al subir el archivo a S3."""

    fallo_registro_bd = 10
    """Error al registrar el adjunto en la base de datos."""

    # -- Extracción de XMLs embebidos (EXTRACCION_ZIP) --
    xml_embebido_no_encontrado = 11
    """No se encontraron los XMLs de Invoice o ApplicationResponse embebidos."""

    xml_embebido_parse_error = 12
    """Error al parsear el XML AttachedDocument para extraer embebidos."""

    # -- Emparejamiento XML/PDF --
    pdf_faltante = 13
    """No se encontró un PDF correspondiente al XML."""

    pdf_sin_xml = 14
    """Se encontró un PDF sin XML correspondiente."""

    # -- Filtro de facturación --
    correo_sin_adjuntos_validos = 15
    """El correo de facturación no contiene adjuntos válidos (ZIP, XML o PDF)."""

    correo_rechazado_filtro = 16
    """El correo no cumple los criterios del filtro de facturación."""

    # -- Errores generales --
    error_procesamiento_general = 17
    """Error inesperado durante el procesamiento del correo."""

    adjunto_duplicado = 18
    """El adjunto ya fue procesado previamente (hash duplicado)."""


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
