"""Metadatos para el filtrado de eventos oficiales de la DIAN."""

class EventosDianMetadata:
    """Configuración de remitentes y códigos permitidos para eventos DIAN."""

    remitentes_autorizados = [
        'facturacionelectronicaqx@gmail.com',
        'FacturaCTSColombia@cenbiz.com',
        'FacturaCTSColombia@cenbiz',
    ]
    """Lista de correos autorizados para enviar notificaciones de eventos (CEN Financiero)."""

    codigos_permitidos = {'030', '032', '033'}
    """Códigos de evento DIAN permitidos para sincronización con factura_control."""

    nombres_eventos = {
        '030': 'Acuse de recibo de Factura Electrónica de Venta',
        '032': 'Recibo del bien o prestación del servicio',
        '033': 'Aceptación expresa',
    }
    """Mapeo de códigos a nombres amigables (informativo)."""
