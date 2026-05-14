"""Metadatos para el formato visual y textos estáticos del reporte Excel.

Este archivo centraliza la configuración de la empresa, títulos de reporte
y anchos de columna para asegurar consistencia en la exportación."""


class EstilosExcel:
    """Configuración de textos y dimensiones para el reporte Excel."""

    nombre_empresa = "QUIPUX SAS"
    """Textos de encabezado nombre empresa."""

    titulo_reporte_base = "RELACIÓN ENTREFA FACTURAS PROCESO DE COMPRAS A CONTABILIDAD {MONTH} {YEAR}"
    """Textos de encabezado título reporte."""

    anchos_fijos = {
        "FECHA EMISIÓN FACTURA DEL PROVEEDOR": 15,
        "FECHA ENTREGA FACTURA A CONTABILIDAD": 15,
        "NIT": 12,
        "NO. FACTURA": 17,
        "FORMA DE PAGO": 22,
        "NOMBRE DE QUIÉN RECIBE EN CONTABILIDAD": 32,
        "DESCRIPCION": 32,
        "ACUSE DE RECIBIDO": 12,
        "RECIBO DE BIEN Y/O SERVICIO": 12,
        "ACEPTACION EXPRESA": 12,
        "EVENTO DIAN": 12,
        "OBSERVACIONES": 52,
    }
    """Configuración de anchos de columna (basado en caracteres)."""

    font_name = "Aptos Narrow"
    """Estilos de fuente nombre."""

    font_size = 8
    """Estilos de fuente tamaño."""

    header_bg_color = "0070C0"
    """Color de fondo del encabezado."""
    header_font_color = "FFFFFF"
    """Color de la fuente del encabezado."""

    body_bg_color = "0070C0"
    """Color de fondo del cuerpo."""

    body_font_color = "FFFFFF"
    """Color de la fuente del cuerpo."""
