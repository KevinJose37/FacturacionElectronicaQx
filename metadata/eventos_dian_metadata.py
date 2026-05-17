"""Metadatos para el filtrado de eventos oficiales de la DIAN."""

class EventosDianMetadata:
    """Configuración de remitentes y códigos permitidos para eventos DIAN."""

    remitentes_autorizados = [
        'facturacionelectronicaqx@gmail.com',
        'FacturaCTSColombia@cenbiz.com',
        'FacturaCTSColombia@cenbiz',
    ]
    """Lista de correos autorizados para enviar notificaciones de eventos (CEN Financiero)."""

    codigos_control = {'030', '032', '033'}
    """Códigos de evento DIAN permitidos para sincronización con factura_control."""

    codigos_nombres = {
        '02': 'Documento validado por la DIAN',
        '04': 'Documento rechazado por la DIAN',
        '030': 'Acuse de recibo',
        '031': 'Reclamo / Rechazo',
        '032': 'Recibo del bien o servicio',
        '033': 'Aceptación expresa',
        '034': 'Aceptación tácita',
    }

    """Mapeo de códigos a nombres amigables (informativo)."""
