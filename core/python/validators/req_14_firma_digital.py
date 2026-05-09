"""Módulo que contiene funciones de validación de la firma digital de la factura."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree
from metadata.db_metadata import IdTipoError

# Local application imports
from core.python.utils.validacion import (
    extraer_nodo_firma,
    extraer_certificado_firma,
    validar_vigencia_certificado,
    validar_firma_criptografica_y_confianza,
)


logger = logging.getLogger(__name__)


def validar_firma_digital_v1(
    xml_invoice: etree._Element | None,
    ruta_ca_confiable: str | None = None,
) -> dict:
    """Valida la firma digital de la factura electrónica según la resolución
     000165 de 2023.
     
    Args:
        xml_invoice: Árbol XML de la factura electrónica a validar.
        ruta_ca_confiable: Ruta al archivo PEM de las CA raíz confiables.
            Si es None, solo se valida presencia y vigencia del certificado.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si la firma digital es válida.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con información del certificado.
    """

    NAMESPACES_FIRMA = {
        'ds': 'http://www.w3.org/2000/09/xmldsig#',
        'xades': 'http://uri.etsi.org/01903/v1.3.2#',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    }

    resultado_validacion = False
    hash_firma = None
    emisor_certificado = None
    sujeto_certificado = None
    vigente_desde = None
    vigente_hasta = None

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar firma digital.'

    else:
        nodo_firma = extraer_nodo_firma(xml_invoice, NAMESPACES_FIRMA)

        if nodo_firma is None:
            mensaje = 'No se encontró la firma digital (ds:Signature) en el XML.'

        else:
            # Extraer el hash de la firma (SignatureValue)
            nodos_sig_value = nodo_firma.xpath(
                './ds:SignatureValue', namespaces=NAMESPACES_FIRMA
            )
            if nodos_sig_value and nodos_sig_value[0].text:
                hash_firma = nodos_sig_value[0].text.strip()[:128]

            # Extraer y validar el certificado
            certificado = extraer_certificado_firma(nodo_firma, NAMESPACES_FIRMA)

            if certificado is None:
                mensaje = (
                    'Se encontró firma digital pero no se pudo extraer '
                    'el certificado X.509.'
                )

            else:
                # Extraer datos del certificado
                emisor_certificado = str(certificado.issuer)
                sujeto_certificado = str(certificado.subject)
                vigente_desde = certificado.not_valid_before_utc.isoformat()
                vigente_hasta = certificado.not_valid_after_utc.isoformat()

                # Validar vigencia
                vigencia_ok, msg_vigencia = validar_vigencia_certificado(certificado)

                if not vigencia_ok:
                    mensaje = msg_vigencia

                elif ruta_ca_confiable:
                    # Validar firma criptográfica + cadena de confianza
                    firma_ok, msg_firma = validar_firma_criptografica_y_confianza(
                        xml_invoice, ruta_ca_confiable
                    )

                    if firma_ok:
                        resultado_validacion = True
                        mensaje = (
                            'Firma digital válida: certificado vigente '
                            'y firma verificada.'
                        )
                    else:
                        mensaje = msg_firma

                else:
                    # Sin CA: solo validamos presencia + vigencia
                    resultado_validacion = True
                    mensaje = (
                        'Firma digital presente y certificado vigente. '
                        'No se validó la cadena de confianza '
                        '(RUTA_CA_CONFIABLE_XML_DSIG no configurada).'
                    )

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'id_error': IdTipoError.firma_digital_invalida if not resultado_validacion else None,
        'datos': {
            'hash_firma_digital': hash_firma,
            'emisor_certificado': emisor_certificado,
            'sujeto_certificado': sujeto_certificado,
            'vigente_desde': vigente_desde,
            'vigente_hasta': vigente_hasta,
        }
    }

    return resultado
