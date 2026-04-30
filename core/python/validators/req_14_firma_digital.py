"""Módulo que contiene funciones de validación de la firma digital de la factura."""

# Standard library imports
import os

# Third-party imports
from lxml import etree


def validar_firma_digital_v1(xml_factura: etree._Element) -> bool:
    """Valida la firma digital del facturador electrónico, su certificado,
    la integridad del documento y la cadena de confianza según la resolución
    000165 de 2023.

    Args:
        xml_factura: Elemento raíz del XML de la factura (Invoice).

    Returns:
        True si la firma digital es válida, False en caso contrario.
    """

    NAMESPACES = {
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'ds': 'http://www.w3.org/2000/09/xmldsig#',
    }

    resultado_validacion = False
    RUTA_CA_CONFIABLE_XML_DSIG = os.getenv("RUTA_CA_CONFIABLE_XML_DSIG", "").strip()

    nodo_firma = extraer_nodo_firma(xml_factura, NAMESPACES)

    if nodo_firma is None:
        mensaje = (
            'No se encontró la firma digital del facturador electrónico '
            '(ds:Signature en ext:UBLExtensions).'
        )

    else:
        certificado = extraer_certificado_firma(nodo_firma, NAMESPACES)

        if certificado is None:
            mensaje = (
                'Se encontró la firma digital, pero no fue posible extraer el certificado'
                ' (ds:X509Certificate).'
            )

        else:
            certificado_vigente, mensaje_certificado = validar_vigencia_certificado(
                certificado
            )

            if not certificado_vigente:
                mensaje = mensaje_certificado

            else:
                firma_valida, mensaje_firma = validar_firma_criptografica_y_confianza(
                    xml_factura=xml_factura,
                    ruta_ca_confiable=RUTA_CA_CONFIABLE_XML_DSIG,
                )

                if firma_valida:
                    resultado_validacion = True
                    mensaje = (
                        'La firma digital del facturador electrónico es válida. '
                        'Se verificó la integridad del documento (DigestValue), la firma '
                        'criptográfica (SignatureValue), la vigencia del certificado y la'
                        ' cadena de confianza.'
                    )

                else:
                    mensaje = mensaje_firma

    enviar_log_validacion(mensaje)

    return resultado_validacion
