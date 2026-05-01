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
    }
    """Diccionario etapa → (código, descripción, severidad). Usado en validaciones_service.py para la página de reglas."""
