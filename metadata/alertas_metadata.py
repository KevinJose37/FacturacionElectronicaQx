"""Metadatos del sistema de alertas.

Constantes de tipos, prioridades, colores y textos de título
para las alertas del sistema de facturación electrónica.

Corresponden a las tablas:
    - FACTURACION.TIPO_PRIORIDAD_ALERTA
    - FACTURACION.TIPO_ALERTA
"""


class CodigoPrioridad:
    """Niveles de prioridad de alertas.

    Solo CRITICA dispara envío de correo electrónico.
    """

    critica = 'CRITICA'
    """Requiere acción inmediata. Envía correo."""

    alta = 'ALTA'
    """Requiere atención pronto."""

    media = 'MEDIA'
    """Informativa con acción sugerida."""

    baja = 'BAJA'
    """Solo informativa."""

    TODOS = {'CRITICA', 'ALTA', 'MEDIA', 'BAJA'}

    COLORES_UI = {
        'CRITICA': '#EF4444',
        'ALTA': '#F59E0B',
        'MEDIA': '#3B82F6',
        'BAJA': '#6B7280',
    }

    @classmethod
    def es_valido(cls, codigo: str) -> bool:
        """Verifica si un código de prioridad es válido."""
        return codigo in cls.TODOS


class CodigoTipoAlerta:
    """Tipos de alerta del sistema.

    Cada tipo tiene una prioridad por defecto asignada en el catálogo de BD.
    """

    # -- Prioridad CRITICA (envían correo) --
    malware_detectado = 'MALWARE_DETECTADO'
    """Archivo infectado con virus o malware."""

    bot_inactivo = 'BOT_INACTIVO'
    """El bot de extracción dejó de funcionar."""

    conexion_fallida = 'CONEXION_FALLIDA'
    """Fallo de conexión a servicio externo (IMAP, BD, S3)."""

    # -- Prioridad ALTA --
    factura_rechazada = 'FACTURA_RECHAZADA'
    """Factura no pasó las validaciones DIAN."""

    vencimiento_proximo = 'VENCIMIENTO_PROXIMO'
    """Factura próxima a vencer sin evento de aceptación DIAN."""

    max_reintentos = 'MAX_REINTENTOS'
    """Factura agotó el máximo de reintentos de procesamiento."""

    # -- Prioridad MEDIA --
    zip_incompleto = 'ZIP_INCOMPLETO'
    """ZIP sin pares XML+PDF válidos."""

    pdf_faltante = 'PDF_FALTANTE'
    """Factura procesada sin PDF adjunto."""

    correo_sin_adjuntos = 'CORREO_SIN_ADJUNTOS'
    """Correo de facturación sin adjuntos válidos."""

    # -- Prioridad BAJA --
    validacion_parcial = 'VALIDACION_PARCIAL'
    """Factura registrada con algunas validaciones fallidas."""

    duplicado_detectado = 'DUPLICADO_DETECTADO'
    """Factura duplicada detectada y omitida."""

    # Mapeo tipo → prioridad por defecto (espejo del catálogo de BD).
    # Se usa como fallback cuando no se puede consultar la tabla.
    PRIORIDAD_DEFAULT = {
        'MALWARE_DETECTADO': 'CRITICA',
        'BOT_INACTIVO': 'CRITICA',
        'CONEXION_FALLIDA': 'CRITICA',
        'FACTURA_RECHAZADA': 'ALTA',
        'VENCIMIENTO_PROXIMO': 'ALTA',
        'MAX_REINTENTOS': 'ALTA',
        'ZIP_INCOMPLETO': 'MEDIA',
        'PDF_FALTANTE': 'MEDIA',
        'CORREO_SIN_ADJUNTOS': 'MEDIA',
        'VALIDACION_PARCIAL': 'BAJA',
        'DUPLICADO_DETECTADO': 'BAJA',
    }


class TitulosAlerta:
    """Plantillas de título para cada tipo de alerta.

    Usan str.format() con los datos del contexto.
    """

    malware_detectado = 'Malware detectado en {archivo}'
    bot_inactivo = 'Bot de extracción inactivo ({minutos} min sin actividad)'
    conexion_fallida = 'Fallo de conexión: {servicio}'
    factura_rechazada = 'Factura rechazada: {motivo}'
    vencimiento_proximo = 'Factura {numero_factura} vence en {dias} días'
    max_reintentos = 'Máximo de reintentos excedido (CUFE: {cufe})'
    zip_incompleto = 'ZIP incompleto: {motivo}'
    pdf_faltante = 'PDF faltante en factura'
    correo_sin_adjuntos = 'Correo sin adjuntos válidos'
    validacion_parcial = 'Factura {numero_factura} con validaciones fallidas'
    duplicado_detectado = 'Factura duplicada omitida (CUFE: {cufe})'


class MensajesAlerta:
    """Mensajes de log relacionados con el sistema de alertas."""

    alerta_creada = 'Alerta creada: tipo=%s prioridad=%s titulo=%s'
    alerta_email_enviado = 'Correo de alerta CRITICA enviado: %s'
    alerta_email_error = 'Error enviando correo de alerta: %s'
    alerta_persistencia_error = 'Error al persistir alerta en BD: %s'
