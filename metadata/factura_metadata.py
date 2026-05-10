"""Metadatos de facturación electrónica.

Define tipos de documento, estados de factura y criterios de ordenamiento
utilizados en servicios y herramientas del chatbot.

Esquema actual — TIPO_ESTADO_PROCESO:
  1=PENDIENTE, 2=EN_PROCESO, 3=PROCESADO, 4=ERROR, 5=FALLIDO

Tipo documento — TIPO_DOCUMENTO_DIAN (códigos):
  01=FE Venta, 02=FE Exportación, 03=Instrumento, 04=FE tipo 04,
  91=Nota Crédito, 92=Nota Débito, 96=Eventos
"""


class TiposDocumento:
    """Mapeo de códigos de tipo de documento DIAN a nombres legibles."""

    FE = 'Factura electrónica'
    """Factura electrónica de venta. Usado en dashboard y chat tools."""

    NC = 'Nota crédito'
    """Nota crédito electrónica. Usado en dashboard y chat tools."""

    ND = 'Nota débito'
    """Nota débito electrónica. Usado en dashboard y chat tools."""

    DS = 'Documento soporte'
    """Documento soporte en adquisiciones. Usado en dashboard y chat tools."""

    # Mapeo código DIAN → nombre legible
    mapa = {
        '01': FE,
        '02': 'Factura electrónica (exportación)',
        '03': 'Instrumento electrónico',
        '04': FE,
        '91': NC,
        '92': ND,
        '96': 'Eventos (ApplicationResponse)',
        # Compatibilidad con códigos antiguos
        'FE': FE,
        'NC': NC,
        'ND': ND,
        'DS': DS,
    }
    """Diccionario código → nombre legible. Usado en chat/tools.py y dashboard_service.py."""


class EstadosFactura:
    """Mapeo de estados de factura a IDs de TIPO_ESTADO_PROCESO.

    Estados actuales:
        1=PENDIENTE, 2=EN_PROCESO, 3=PROCESADO, 4=ERROR, 5=FALLIDO
    """

    validada = (3,)
    """IDs de estado para facturas procesadas/validadas."""

    rechazada = (4, 5)
    """IDs de estado para facturas con error o fallidas."""

    pendiente = (1, 2)
    """IDs de estado para facturas pendientes o en proceso."""

    error = (4, 5)
    """IDs de estado para facturas con error."""

    mapa_ids = {
        'validada': validada,
        'rechazada': rechazada,
        'pendiente': pendiente,
        'error': error,
    }
    """Mapeo nombre → tupla de IDs. Usado en chat/tools.py y facturas_service.py para filtros SQL."""

    mapa_texto = {
        1: 'pendiente',
        2: 'pendiente',
        3: 'validada',
        4: 'rechazada',
        5: 'error',
    }
    """Mapeo ID → texto de estado. Usado en facturas_service.py para la respuesta de la API."""

    mapa_descripcion = {
        'Pendiente de procesamiento': 'pendiente',
        'En proceso de ingesta': 'pendiente',
        'Procesado de ingesta': 'validada',
        'Estado de error en el procesamiento': 'rechazada',
        'Estado de fallo definitivo (agotó reintentos)': 'error',
    }
    """Mapeo descripción BD → estado normalizado. Usado en dashboard_service.py para últimas facturas."""


class OrdenFacturas:
    """Mapeo de criterios de ordenamiento a cláusulas SQL ORDER BY."""

    reciente = 'f.fecha_creacion DESC'
    """Ordenar por fecha de creación descendente (más recientes primero)."""

    antiguo = 'f.fecha_creacion ASC'
    """Ordenar por fecha de creación ascendente (más antiguos primero)."""

    monto_alto = 'f.valor_total DESC'
    """Ordenar por monto total descendente (mayor valor primero)."""

    monto_bajo = 'f.valor_total ASC'
    """Ordenar por monto total ascendente (menor valor primero)."""

    mapa = {
        'reciente': reciente,
        'antiguo': antiguo,
        'monto_alto': monto_alto,
        'monto_bajo': monto_bajo,
    }
    """Diccionario criterio → cláusula SQL. Usado en chat/tools.py para buscar_facturas."""
