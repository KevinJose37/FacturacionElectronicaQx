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
)


logger = logging.getLogger(__name__)


def validar_firma_digital_v1(
    xml_invoice: etree._Element | None,
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
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
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

                # Extraer fecha de firma o emisión como fecha de referencia
                fecha_ref = None
                nodos_signing_time = xml_invoice.xpath(
                    './/xades:SigningTime',
                    namespaces=NAMESPACES_FIRMA
                )
                if nodos_signing_time and nodos_signing_time[0].text:
                    try:
                        val = nodos_signing_time[0].text.strip()
                        if val[-3] == ':' and (val[-6] == '+' or val[-6] == '-'):
                            val = val[:-3] + val[-2:]
                        from datetime import datetime, timezone
                        fecha_ref = datetime.fromisoformat(val).astimezone(timezone.utc)
                    except Exception:
                        pass

                if not fecha_ref:
                    # Fallback al IssueDate de la factura
                    issue_date = xml_invoice.xpath('./cbc:IssueDate', namespaces=NAMESPACES_FIRMA)
                    issue_time = xml_invoice.xpath('./cbc:IssueTime', namespaces=NAMESPACES_FIRMA)
                    if issue_date and issue_date[0].text:
                        try:
                            date_str = issue_date[0].text.strip()
                            time_str = issue_time[0].text.strip() if issue_time and issue_time[0].text else "00:00:00-05:00"
                            dt_str = f"{date_str}T{time_str}"
                            if dt_str[-3] == ':' and (dt_str[-6] == '+' or dt_str[-6] == '-'):
                                dt_str = dt_str[:-3] + dt_str[-2:]
                            from datetime import datetime, timezone
                            fecha_ref = datetime.fromisoformat(dt_str).astimezone(timezone.utc)
                        except Exception:
                            pass

                # Validar vigencia
                vigencia_ok, msg_vigencia = validar_vigencia_certificado(certificado, fecha_ref)

                if not vigencia_ok:
                    mensaje = msg_vigencia
                else:
                    resultado_validacion = True
                    mensaje = (
                        'Firma digital presente y certificado vigente.'
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
