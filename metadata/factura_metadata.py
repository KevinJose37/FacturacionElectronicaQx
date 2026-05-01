"""Metadatos de facturación electrónica.

Define tipos de documento, estados de factura y criterios de ordenamiento
utilizados en servicios y herramientas del chatbot.
"""


class TiposDocumento:
    """Mapeo de códigos de tipo de documento a nombres legibles."""

    FE = 'Factura electrónica'
    """Factura electrónica de venta. Usado en dashboard y chat tools."""

    NC = 'Nota crédito'
    """Nota crédito electrónica. Usado en dashboard y chat tools."""

    ND = 'Nota débito'
    """Nota débito electrónica. Usado en dashboard y chat tools."""

    DS = 'Documento soporte'
    """Documento soporte en adquisiciones. Usado en dashboard y chat tools."""

    mapa = {'FE': FE, 'NC': NC, 'ND': ND, 'DS': DS}
    """Diccionario código → nombre legible. Usado en chat/tools.py y dashboard_service.py."""


class EstadosFactura:
    """Mapeo de estados de factura a IDs de proceso en TIPO_ESTADO_PROCESO."""

    validada = (7, 9)
    """IDs de estado para facturas validadas (VALIDADO_DIAN, PERSISTIDO)."""

    rechazada = (8, 10)
    """IDs de estado para facturas rechazadas (RECHAZADO_DIAN, ERROR)."""

    pendiente = (5, 6)
    """IDs de estado para facturas pendientes (XML_EXTRAIDO, FACTURA_PARSED)."""

    error = (10,)
    """IDs de estado para facturas con error."""

    mapa_ids = {
        'validada': validada,
        'rechazada': rechazada,
        'pendiente': pendiente,
        'error': error,
    }
    """Mapeo nombre → tupla de IDs. Usado en chat/tools.py y facturas_service.py para filtros SQL."""

    mapa_texto = {
        7: 'validada', 8: 'rechazada', 9: 'validada',
        10: 'error', 5: 'pendiente', 6: 'pendiente',
    }
    """Mapeo ID → texto de estado. Usado en facturas_service.py para la respuesta de la API."""

    mapa_descripcion = {
        'Validado por DIAN': 'validada',
        'Rechazado por DIAN': 'rechazada',
        'Error en el proceso': 'error',
        'Persistido en BD': 'validada',
        'XML parseado': 'pendiente',
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
