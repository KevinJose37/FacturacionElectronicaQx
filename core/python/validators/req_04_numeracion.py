"""Módulo que contiene funciones de validación para la numeración de facturas."""

# Third-party imports
from lxml import etree


def validar_numeracion_dian_v1(xml_factura: etree._Element) -> bool:
    """Valida la numeración DIAN de la factura electrónica según la resolución
    000165 de 2023.
    
    Args:
        xml_factura: Árbol XML de la factura electrónica a validar.

    Reglas:
    - Debe existir número de factura
    - Debe existir autorización DIAN
    - Debe existir rango (From, To)
    - Si hay prefijo, debe ser consistente
    - El número debe estar dentro del rango autorizado

    Retorna:
        True si la numeración es válida, False en caso contrario.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'sts': 'dian:gov:co:facturaelectronica:Structures-2-1'
    }

    nodo_id = xml_factura.xpath('./cbc:ID', namespaces=NAMESPACES)
    id_factura = (nodo_id[0].text or '').strip() if nodo_id else None
    prefijo_scheme = nodo_id[0].get('schemeID') if nodo_id else None

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

    rango_from = (nodo_from[0].text or '').strip() if nodo_from else None
    rango_to = (nodo_to[0].text or '').strip() if nodo_to else None
    prefijo_dian = (nodo_prefix[0].text or '').strip() if nodo_prefix else None

    resultado_validacion = False

    if not id_factura:
        mensaje = 'No se encontró número de factura (cbc:ID).'

    elif not autorizacion:
        mensaje = f'Factura "{id_factura}" sin número de autorización DIAN.'

    elif not rango_from or not rango_to:
        mensaje = f'Factura "{id_factura}" sin rango autorizado DIAN.'

    else:
        prefijo_detectado = ''
        numero_str = id_factura

        if prefijo_dian and id_factura.startswith(prefijo_dian):
            prefijo_detectado = prefijo_dian
            numero_str = id_factura[len(prefijo_dian):]

        elif prefijo_scheme:
            prefijo_detectado = prefijo_scheme

            if id_factura.startswith(prefijo_scheme):
                numero_str = id_factura[len(prefijo_scheme):]

        if not numero_str.isdigit():
            mensaje = (f'Factura "{id_factura}" tiene un consecutivo no numérico.')

        else:
            numero = int(numero_str)

            try:
                rango_inicio = int(rango_from)
                rango_fin = int(rango_to)

            except ValueError:
                mensaje = (
                    f'Factura "{id_factura}" tiene rango DIAN inválido '
                    f'({rango_from}-{rango_to}).'
                )

            else:
                if not (rango_inicio <= numero <= rango_fin):
                    mensaje = (
                        f'Factura "{id_factura}" fuera de rango autorizado '
                        f'({rango_inicio}-{rango_fin}).'
                    )

                elif prefijo_dian and prefijo_detectado != prefijo_dian:
                    mensaje = (
                        f'Factura "{id_factura}" con prefijo inconsistente. '
                        f'Esperado: "{prefijo_dian}", encontrado: "{prefijo_detectado}".'
                    )

                else:
                    mensaje = (
                        f'Numeración válida: factura "{id_factura}", '
                        f'autorización {autorizacion}, rango {rango_inicio}-{rango_fin}.'
                    )
                    resultado_validacion = True

    enviar_log_validacion(mensaje)

    return resultado_validacion
