"""Metadatos de reglas de validación del pipeline de facturación."""


class ReglasValidacion:
    """Mapeo de etapas de proceso a reglas de validación.

    Cada entrada contiene: (código_regla, descripción, severidad).
    """

    mapa = {
        'RECEPCION': ('VAL-001', 'Correo recibido y clasificado', 'medium'),
        'VERIFICACION_ADJUNTO': ('VAL-002', 'Adjunto verificado (ZIP válido)', 'high'),
        'ESCANEO': ('VAL-003', 'Escaneo de seguridad (antimalware)', 'high'),
        'EXTRACCION_XML': ('VAL-004', 'XML extraído del archivo comprimido', 'medium'),
        'PARSEO': ('VAL-005', 'XML parseado (estructura válida)', 'high'),
        'VALIDACION_DIAN': ('VAL-006', 'Validación CUFE con DIAN', 'high'),
        'PERSISTENCIA': ('VAL-007', 'Persistido en base de datos', 'low'),
        
        # Reglas reales correspondientes a la base de datos
        'ESCANEO_MALWARE': ('EXT-MAL', 'Escaneo de virus y malware', 'high'),
        'DESCARGA_ALMACENAMIENTO': ('EXT-S3', 'Almacenamiento seguro en S3', 'medium'),
        'VALIDACION_CONTENIDO_ZIP': ('VAL-ZIP', 'Validación de contenido ZIP', 'high'),
        'EXTRACCION_ZIP': ('EXT-ZIP', 'Extracción de archivos del ZIP', 'medium'),
        'REGISTRO_ADJUNTOS': ('EXT-BD', 'Registro de adjuntos en BD', 'low'),
        'VALIDACION_CUFE': ('VAL-CUF', 'Validación y extracción de CUFE', 'high'),
        'VALIDACION_DENOMINACION': ('VAL-DEN', 'Validación de denominación', 'medium'),
        'EXTRACCION_EMISOR': ('EXT-EMI', 'Extracción de datos del emisor', 'medium'),
        'EXTRACCION_ADQUIRIENTE': ('EXT-ADQ', 'Extracción de datos del adquiriente', 'medium'),
        'VALIDACION_NUMERACION': ('VAL-NUM', 'Validación de rango de numeración', 'high'),
        'VALIDACION_FECHA_GENERACION': ('VAL-FGE', 'Validación de fecha de generación', 'medium'),
        'VALIDACION_FECHA_VALIDACION': ('VAL-FVA', 'Validación de fecha de expedición DIAN', 'medium'),
        'VALIDACION_DOCUMENTO_DIAN': ('VAL-DIA', 'Validación de documento DIAN', 'high'),
        'EXTRACCION_LINEAS': ('EXT-LIN', 'Extracción de líneas e ítems', 'medium'),
        'VALIDACION_VALOR_TOTAL': ('VAL-TOT', 'Validación de montos totales', 'high'),
        'EXTRACCION_FORMA_PAGO': ('EXT-FPA', 'Extracción de forma de pago', 'medium'),
        'EXTRACCION_MEDIO_PAGO': ('EXT-MPA', 'Extracción de medio de pago', 'medium'),
        'EXTRACCION_CALIDAD_TRIBUTARIA': ('EXT-TRI', 'Extracción de calidad tributaria', 'medium'),
        'EXTRACCION_IMPUESTOS': ('EXT-IMP', 'Extracción de impuestos y retenciones', 'medium'),
        'VALIDACION_FIRMA_DIGITAL': ('VAL-FIR', 'Validación de firma digital', 'high'),
        'EXTRACCION_QR': ('EXT-QR', 'Extracción y validación de QR', 'medium'),
        'VALIDACION_ANEXO_TECNICO': ('VAL-UBL', 'Validación de anexo técnico UBL', 'high'),
        'EXTRACCION_SOFTWARE': ('EXT-SOF', 'Extracción de datos del software', 'medium'),
        'REGISTRO_FACTURA': ('EXT-REG', 'Registro definitivo de factura', 'high'),
        'VERIFICACION_GRAFICA': ('VAL-PDF', 'Verificación gráfica PDF vs XML', 'high'),
        'FILTRO_RECEPCION': ('VAL-FIL', 'Evaluación de filtro de recepción', 'medium'),
    }
    """Diccionario etapa → (código, descripción, severidad). Usado en validaciones_service.py para la página de reglas."""
