"""Metadatos para el módulo de alertas DIAN. 
Etiquetas descriptivas para los tipos de alertas generadas."""


class EtiquetasAlerta:
    """Etiquetas de visualización para las alertas de eventos DIAN."""

    sin_evento_030 = 'Facturas sin evento DIAN 030 (Acuse de recibo)'
    """Etiqueta alerta sin evento DIAN 030."""

    sin_evento_032 = 'Facturas sin evento DIAN 032 (Recibo del bien)'
    """Etiqueta alerta sin evento DIAN 032."""

    sin_evento_033 = 'Facturas sin evento DIAN 033 (Aceptación expresa)'
    """Etiqueta alerta sin evento DIAN 033."""

    con_evento_rechazo = 'Facturas con evento DIAN de rechazo (031 Reclamo)'
    """Etiqueta alerta con evento DIAN de rechazo."""

    mapa = {
        'sin_evento_030': sin_evento_030,
        'sin_evento_032': sin_evento_032,
        'sin_evento_033': sin_evento_033,
        'con_evento_rechazo': con_evento_rechazo,
    }
    """Mapa de etiquetas de visualización para las alertas de eventos DIAN."""


class ConfigScheduler:
    """Configuración del programador de alertas."""

    hora_ejecucion = None
    """Ejecución por intervalos horaria."""

    minuto_ejecucion = 0
    """Minuto de ejecución."""

    segundos_espera = 60
    """Intervalo de verificación en el bucle principal."""
