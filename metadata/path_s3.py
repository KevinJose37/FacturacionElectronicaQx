"""Metadatos de rutas S3 para almacenamiento de archivos."""


class RutasS3:
    """Plantillas de rutas para almacenar adjuntos en S3.

    Las rutas se construyen de forma jerárquica y reutilizable:
        base               -> quipux/facturacion_electronica
        raw                -> {base}/raw
        adjuntos_factura   -> {raw}/adjuntos_factura
        zip / xml / pdf    -> {adjuntos_factura}/<tipo>/{year}/{month}/{day}/{nombre_descarga}
    """

    # Ruta raíz reutilizable del dominio de facturación electrónica.
    base = "quipux/facturacion_electronica"
    """Ruta base del dominio de facturación electrónica."""

    # Subruta para datos crudos (sin transformar).
    raw = f"{base}/raw"
    """Subruta para datos crudos descargados directamente de la fuente."""

    # Subruta para los adjuntos de factura dentro de los datos crudos.
    adjuntos_factura = f"{raw}/adjuntos_factura"
    """Subruta para los adjuntos (zip, xml, pdf) asociados a una factura."""

    zip = f"{adjuntos_factura}/zip/{{year}}/{{month}}/{{day}}/{{nombre_descarga}}"
    """Ruta para archivos ZIP descargados."""

    xml = f"{adjuntos_factura}/xml/{{year}}/{{month}}/{{day}}/{{nombre_descarga}}"
    """Ruta para archivos XML extraídos."""

    pdf = f"{adjuntos_factura}/pdf/{{year}}/{{month}}/{{day}}/{{nombre_descarga}}"
    """Ruta para archivos PDF extraídos."""
