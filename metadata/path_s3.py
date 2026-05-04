"""Metadatos de rutas S3 para almacenamiento de archivos."""


class RutasS3:
    """Plantillas de rutas para almacenar adjuntos en S3."""

    base = "quipux/facturacion_electronica"
    """Ruta base del dominio de facturación electrónica."""

    raw = f"{base}/raw"
    """Subruta para datos crudos descargados directamente de la fuente."""

    adjuntos_factura = f"{raw}/adjuntos_factura"
    """Subruta para los adjuntos (zip, xml, pdf) asociados a una factura."""

    zip = f"{adjuntos_factura}/zip/{{year}}/{{month}}/{{day}}/{{nombre_descarga}}"
    """Ruta para archivos ZIP descargados."""

    xml = f"{adjuntos_factura}/xml/{{year}}/{{month}}/{{day}}/{{nombre_descarga}}"
    """Ruta para archivos XML extraídos."""

    pdf = f"{adjuntos_factura}/pdf/{{year}}/{{month}}/{{day}}/{{nombre_descarga}}"
    """Ruta para archivos PDF extraídos."""

    processed = f"{base}/processed"
    """Subruta para datos procesados (facturas validadas y registradas)."""

    facturas_processed = f"{processed}/facturas"
    """Subruta para facturas procesadas exitosamente."""

    factura_procesada_dir = (
        f"{facturas_processed}/{{proveedor}}/{{year}}/{{month}}/{{day}}"
    )
    """Carpeta destino por proveedor y fecha (sin nombre de archivo)."""

    zip_procesado = f"{factura_procesada_dir}/{{nombre_descarga}}"
    """Ruta para el ZIP original de una factura procesada."""

    xml_procesado = f"{factura_procesada_dir}/{{nombre_descarga}}"
    """Ruta para el XML original de una factura procesada."""

    pdf_procesado = f"{factura_procesada_dir}/{{nombre_descarga}}"
    """Ruta para el PDF original de una factura procesada."""
