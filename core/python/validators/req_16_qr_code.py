"""Módulo de validación del código QR en facturas electrónicas."""

# Standard library imports
import re

# Third-party imports
from urllib.parse import urlparse, parse_qs
from lxml import etree


def validar_codigo_qr_v1(xml_factura: etree._Element) -> bool:
    """Valida el código QR de la factura electrónica según la resolución 000165 de 2023.

    Verifica:
    - presencia del nodo sts:QRCode
    - formato de URL válido
    - dominio correspondiente a DIAN (producción o habilitación)
    - presencia del CUFE dentro del QR
    - consistencia con el ambiente del documento

    Args:
        xml_factura: Elemento raíz del XML de la factura (Invoice).

    Returns:
        True si el QR es válido, False en caso contrario.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
    }

    resultado_validacion = False

    nodos_qr = xml_factura.xpath('.//sts:QRCode', namespaces=NAMESPACES)

    cufe_xml = extraer_texto_xpath(xml_factura, './cbc:UUID', NAMESPACES)
    ambiente = extraer_texto_xpath(xml_factura, './cbc:ProfileExecutionID', NAMESPACES)

    if not nodos_qr or not nodos_qr[0].text or not nodos_qr[0].text.strip():
        mensaje = 'No se encontró el código QR en el nodo sts:QRCode.'
    else:
        qr_texto = nodos_qr[0].text.strip()

        try:
            parsed = urlparse(qr_texto)
            es_url_valida = all([parsed.scheme, parsed.netloc])

        except Exception:
            es_url_valida = False

        if not es_url_valida:
            mensaje = 'El contenido del código QR no corresponde a una URL válida.'

        else:
            dominio = parsed.netloc.lower()

            dominios_validos = [
                'catalogo-vpfe.dian.gov.co',
                'catalogo-vpfe-hab.dian.gov.co',
            ]

            if not any(d in dominio for d in dominios_validos):
                mensaje = (
                    'El código QR no apunta a un dominio válido de la DIAN. '
                    f'Dominio encontrado: {dominio}.'
                )
            else:
                query_params = parse_qs(parsed.query)

                cufe_qr = None
                posibles_llaves = ['cufe', 'CUFE', 'uuid', 'UUID']

                for llave in posibles_llaves:
                    if llave in query_params and query_params[llave]:
                        cufe_qr = query_params[llave][0]
                        break

                if not cufe_qr:
                    mensaje = 'El código QR no contiene el CUFE como parámetro.'

                elif not cufe_xml:
                    mensaje = 'No se encontró el CUFE en el XML para validar contra el QR'

                elif cufe_qr.strip().lower() != cufe_xml.strip().lower():
                    mensaje = (
                        'El CUFE contenido en el QR no coincide con el informado en el '
                        f'XML QR: {cufe_qr} - XML: {cufe_xml}.'
                    )

                else:
                    es_habilitacion = 'hab' in dominio
                    es_produccion = not es_habilitacion

                    if ambiente == '1' and not es_produccion:
                        mensaje = (
                            'Inconsistencia: el documento está en producción '
                            '(ProfileExecutionID=1) pero el QR es de habilitación.'
                        )

                    elif ambiente == '2' and not es_habilitacion:
                        mensaje = (
                            'Inconsistencia: el documento está en habilitación '
                            '(ProfileExecutionID=2) pero el QR es de producción.'
                        )

                    else:
                        resultado_validacion = True
                        mensaje = (
                            'El código QR es válido. Se verificó la URL, el dominio '
                            'DIAN, la presencia del CUFE y la consistencia con el '
                            'ambiente.'
                        )

    enviar_log_validacion(mensaje)

    return resultado_validacion
