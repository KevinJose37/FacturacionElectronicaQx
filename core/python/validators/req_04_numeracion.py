"""Módulo que contiene funciones de validación para la numeración de facturas."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree


logger = logging.getLogger(__name__)


def validar_numeracion_dian_v1(xml_factura: etree._Element) -> dict:
    """Valida la numeración DIAN de la factura electrónica según la resolución
    000165 de 2023.
    
    Args:
        xml_factura: Árbol XML de la factura electrónica a validar.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si la numeración es válida.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con autorizacion, prefijo, numero, rango, fechas.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'sts': 'dian:gov:co:facturaelectronica:Structures-2-1'
    }

    nodo_id = xml_factura.xpath('./cbc:ID', namespaces=NAMESPACES)
    id_factura = (nodo_id[0].text or '').strip() if nodo_id else None

    nodo_auth = xml_factura.xpath(
        './/sts:InvoiceControl/sts:InvoiceAuthorization',
        namespaces=NAMESPACES
    )
    autorizacion = (nodo_auth[0].text or '').strip() if nodo_auth else None

    nodo_from = xml_factura.xpath(
        './/sts:InvoiceControl/sts:AuthorizedInvoices/sts:From',
        namespaces=NAMESPACES
    )
    nodo_to = xml_factura.xpath(
        './/sts:InvoiceControl/sts:AuthorizedInvoices/sts:To',
        namespaces=NAMESPACES
    )
    nodo_prefix = xml_factura.xpath(
        './/sts:InvoiceControl/sts:AuthorizedInvoices/sts:Prefix',
        namespaces=NAMESPACES
    )

    # Fechas de vigencia de la autorización
    nodo_start_date = xml_factura.xpath(
        './/sts:InvoiceControl/sts:AuthorizationPeriod/cbc:StartDate',
        namespaces=NAMESPACES
    )
    nodo_end_date = xml_factura.xpath(
        './/sts:InvoiceControl/sts:AuthorizationPeriod/cbc:EndDate',
        namespaces=NAMESPACES
    )

    rango_from = (nodo_from[0].text or '').strip() if nodo_from else None
    rango_to = (nodo_to[0].text or '').strip() if nodo_to else None
    prefijo_dian = (nodo_prefix[0].text or '').strip() if nodo_prefix else None
    fecha_inicio = (nodo_start_date[0].text or '').strip() if nodo_start_date else None
    fecha_fin = (nodo_end_date[0].text or '').strip() if nodo_end_date else None

    resultado_validacion = False
    prefijo_detectado = ''
    numero_consecutivo = None

    if not id_factura:
        mensaje = 'No se encontró número de factura (cbc:ID).'

    elif not autorizacion:
        mensaje = f'Factura "{id_factura}" sin número de autorización DIAN.'

    elif not rango_from or not rango_to:
        mensaje = f'Factura "{id_factura}" sin rango autorizado DIAN.'

    else:
        numero_str = id_factura

        if prefijo_dian and id_factura.startswith(prefijo_dian):
            prefijo_detectado = prefijo_dian
            numero_str = id_factura[len(prefijo_dian):]

        if not numero_str.isdigit():
            mensaje = (f'Factura "{id_factura}" tiene un consecutivo no numérico.')

        else:
            numero_consecutivo = int(numero_str)

            try:
                rango_inicio = int(rango_from)
                rango_fin = int(rango_to)

            except ValueError:
                mensaje = (
                    f'Factura "{id_factura}" tiene rango DIAN inválido '
                    f'({rango_from}-{rango_to}).'
                )

            else:
                if not (rango_inicio <= numero_consecutivo <= rango_fin):
                    mensaje = (
                        f'Factura "{id_factura}" fuera de rango autorizado '
                        f'({rango_inicio}-{rango_fin}).'
                    )

                else:
                    mensaje = (
                        f'Numeración válida: factura "{id_factura}", '
                        f'autorización {autorizacion}, rango {rango_inicio}-{rango_fin}.'
                    )
                    resultado_validacion = True

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'datos': {
            'numero_factura': id_factura,
            'numero_autorizacion': autorizacion,
            'prefijo': prefijo_detectado or prefijo_dian,
            'numero_consecutivo': numero_consecutivo,
            'rango_desde': int(rango_from) if rango_from and rango_from.isdigit() else None,
            'rango_hasta': int(rango_to) if rango_to and rango_to.isdigit() else None,
            'fecha_inicio_vigencia': fecha_inicio,
            'fecha_fin_vigencia': fecha_fin,
        }
    }

    return resultado
