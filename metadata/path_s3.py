"""Metadatos de rutas S3 para almacenamiento de archivos."""

class RutasS3:
    """Plantillas de rutas para almacenar adjuntos en S3."""

    zip = "quipux/facturacion_electronica/raw/adjuntos_factura/zip/{year}/{month}/{day}/{nombre_descarga}"
    """Ruta base para archivos ZIP descargados."""

    xml = "quipux/facturacion_electronica/raw/adjuntos_factura/xml/{year}/{month}/{day}/{nombre_descarga}"
    """Ruta base para archivos XML extraídos."""

    pdf = "quipux/facturacion_electronica/raw/adjuntos_factura/pdf/{year}/{month}/{day}/{nombre_descarga}"
    """Ruta base para archivos PDF extraídos."""
