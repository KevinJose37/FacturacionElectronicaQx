"""Metadatos para el registro de logs de trazabilidad de procesos."""


class EtapasProceso:
    """Códigos de las etapas técnicas del proceso de facturación."""

    recepcion_email = 'RECEPCION_EMAIL'
    """Detección y descarga del correo electrónico."""

    verificacion_adjuntos = 'VERIFICACION_ADJUNTOS'
    """Identificación de archivos ZIP/XML en el correo."""

    escaneo_seguridad = 'ESCANEO_SEGURIDAD'
    """Validación de malware en los archivos recibidos."""

    extraccion_xml = 'EXTRACCION_XML'
    """Extracción del contenido XML de paquetes ZIP."""

    parseo_factura = 'PARSEO_FACTURA'
    """Lectura y extracción de datos del XML de la factura."""

    validacion_dian = 'VALIDACION_DIAN'
    """Consulta de estado y validación normativa ante la DIAN."""

    persistencia_db = 'PERSISTENCIA_DB'
    """Guardado final de la factura y sus detalles en la base de datos."""


class EstadosProceso:
    """Códigos de referencia para los estados del proceso (TIPO_ESTADO_PROCESO)."""

    recibido = 'RECIBIDO'
    """Correo recibido."""

    adjunto_verificado = 'ADJUNTO_VERIFICADO'
    """Adjunto verificado."""

    escaneado_ok = 'ESCANEADO_OK'
    """Archivo sin malware."""

    escaneado_bloqueado = 'ESCANEADO_BLOQUEADO'
    """Archivo con malware."""

    xml_extraido = 'XML_EXTRAIDO'
    """XML extraído."""

    factura_parsed = 'FACTURA_PARSED'
    """XML parseado."""

    validado_dian = 'VALIDADO_DIAN'
    """Validado por DIAN."""

    rechazado_dian = 'RECHAZADO_DIAN'
    """Rechazado por DIAN."""

    persistido = 'PERSISTIDO'
    """Persistido en BD."""

    error = 'ERROR'
    """Error en el proceso."""


class MensajesError:
    """Mensajes predefinidos para el campo DETALLE_ERROR."""

    error_cuerpo_email = 'Falla al obtener el cuerpo del correo via IMAP'
    """Error al intentar leer el contenido RFC822 del servidor."""

    error_sin_zip = 'El correo no contiene el archivo ZIP requerido'
    """No se encontró ningún adjunto con extensión .zip."""


class EstructurasDetalle:
    """Plantillas para el campo DETALLE_JSON en formato string para ser formateadas."""

    recepcion_email = '{{"uid": "{uid}", "host": "{host}"}}'
    """Detalle para la etapa de recepción de correo."""

    verificacion_adjuntos = '{{"archivo_zip": "{archivo_zip}"}}'
    """Detalle para la etapa de verificación de adjuntos."""


class IdProceso:
    """IDs de proceso fijos o de prueba para trazabilidad."""

    ingesta_correos = 1
    """ID de proceso para registrar logs de ingesta."""
