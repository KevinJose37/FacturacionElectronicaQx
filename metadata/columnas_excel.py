"""Metadatos para la generación del reporte Excel y visualización en Front.

Este archivo define el mapeo entre los nombres de las columnas en la base de datos
y sus etiquetas amigables para el usuario final, siguiendo el estándar de clases.
"""

class ColumnasExcel:
    """Mapeo de nombres de columnas de base de datos a etiquetas de reporte."""

    fecha_admision_proveedor = "Fecha admisión factura del proveedor"
    """Fecha de la factura emitida por el proveedor."""

    medio_recepcion = "Medio en que se recibió"
    """Canal por el cual ingresó la factura al sistema."""

    fecha_entrega_contabilidad = "Fecha entrega factura a contabilidad"
    """Fecha en la que el documento se remite al área contable."""

    nombre_recibe_contabilidad = "Nombre de quien recibe en contabilidad"
    """Funcionario que recepciona el documento en contabilidad."""

    nombre_proveedor = "Descripción"
    """Corresponde al nombre o razón social del proveedor."""

    nit_proveedor = "NIT del proveedor"
    """Número de identificación tributaria del emisor."""

    numero_factura = "No. Factura"
    """Número consecutivo de la factura electrónica."""

    forma_pago = "Forma de pago"
    """Condición de pago: CREDITO o CONTADO."""

    acuso_recibido = "Acuso de recibido"
    """Indicador booleano de acuse de recibo."""

    recibido_bien_servicio = "Recibido de bien y/o servicio"
    """Indicador booleano de recibo de bienes o servicios."""

    aceptacion_empresa = "Aceptación empresa"
    """Indicador booleano de aceptación por parte de la empresa."""

    recibido = "Recibido"
    """Indicador general de recepción."""

    observaciones_entrega = "Observaciones"
    """Comentarios sobre la oportunidad de la entrega."""

    eventos_dian_notif = "Eventos DIAN"
    """Notificaciones y eventos registrados ante la DIAN."""

    mapa = {
        "fecha_admision_proveedor": fecha_admision_proveedor,
        "medio_recepcion": medio_recepcion,
        "fecha_entrega_contabilidad": fecha_entrega_contabilidad,
        "nombre_recibe_contabilidad": nombre_recibe_contabilidad,
        "nombre_proveedor": nombre_proveedor,
        "nit_proveedor": nit_proveedor,
        "numero_factura": numero_factura,
        "forma_pago": forma_pago,
        "acuso_recibido": acuso_recibido,
        "recibido_bien_servicio": recibido_bien_servicio,
        "aceptacion_empresa": aceptacion_empresa,
        "recibido": recibido,
        "observaciones_entrega": observaciones_entrega,
        "eventos_dian_notif": eventos_dian_notif
    }
    """Diccionario snake_case -> Etiqueta amigable."""


class MetadatosReporte:
    """Configuración adicional para el comportamiento de columnas en Excel y Front."""

    booleanas = [
        "acuso_recibido",
        "recibido_bien_servicio",
        "aceptacion_empresa",
        "recibido"
    ]
    """Columnas que deben representarse con una 'X' si son True en el reporte."""

    editables = [
        "fecha_entrega_contabilidad",
        "nombre_recibe_contabilidad",
        "acuso_recibido",
        "recibido_bien_servicio",
        "aceptacion_empresa",
        "observaciones_entrega",
        "eventos_dian_notif"
    ]
    """Columnas habilitadas para edición desde el Frontend."""
