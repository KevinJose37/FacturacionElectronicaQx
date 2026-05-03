"""Módulo que contiene funciones de validación del código QR de la factura electrónica."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import extraer_texto_xpath


logger = logging.getLogger(__name__)

NAMESPACES = {
    'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
    'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
    'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
}


def validar_qr_code_v1(
    xml_invoice: etree._Element | None,
    cufe: str | None = None,
) -> dict:
    """Valida el contenido del código QR de la factura electrónica.

    El QR puede estar en dos formatos:
    1. URL con query parameters (ej: https://...?DocumentKey=CUFE&...)
    2. Texto multilínea con clave=valor (estilo DIAN moderno)

    Args:
        xml_invoice: Árbol XML del Invoice a validar.
        cufe: CUFE extraído previamente para validación cruzada.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si el QR es válido.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con contenido del QR y datos extraídos.
    """

    resultado_validacion = False
    contenido_qr = None
    qr_datos = {}

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar QR.'

    else:
        # El QR puede estar en QRCode o en Software
        nodo_qr = xml_invoice.xpath(
            './/sts:QRCode', namespaces=NAMESPACES
        )
        if not nodo_qr:
            nodo_qr = xml_invoice.xpath(
                './/ext:UBLExtensions//sts:QRCode', namespaces=NAMESPACES
            )

        contenido_qr = (
            (nodo_qr[0].text or '').strip() if nodo_qr else None
        )

        if not contenido_qr:
            mensaje = 'No se encontró el código QR (sts:QRCode) en el XML.'

        else:
            # Intentar parsear como URL con query params
            if '?' in contenido_qr and '=' in contenido_qr:
                try:
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(contenido_qr)
                    params = parse_qs(parsed.query)
                    for key, values in params.items():
                        qr_datos[key] = values[0] if values else ''
                except Exception:
                    pass

            # Intentar parsear como texto multilínea (clave\nvalor o clave=valor)
            if not qr_datos:
                lineas = contenido_qr.replace('\r', '').split('\n')
                for linea in lineas:
                    linea = linea.strip()
                    if '=' in linea:
                        key, _, val = linea.partition('=')
                        qr_datos[key.strip()] = val.strip()
                    elif ':' in linea:
                        key, _, val = linea.partition(':')
                        qr_datos[key.strip()] = val.strip()

            # Validación cruzada con CUFE
            cufe_en_qr = qr_datos.get('DocumentKey') or qr_datos.get('CUFE')
            if cufe and cufe_en_qr:
                if cufe.lower() == cufe_en_qr.lower():
                    resultado_validacion = True
                    mensaje = 'Código QR válido: CUFE coincide.'
                else:
                    mensaje = (
                        f'QR presente pero CUFE no coincide.\n'
                        f'  QR: {cufe_en_qr[:20]}...\n'
                        f'  Factura: {cufe[:20]}...'
                    )
                    resultado_validacion = True  # QR presente, advertencia

            else:
                resultado_validacion = True
                mensaje = 'Código QR presente.'

                if cufe and not cufe_en_qr:
                    mensaje += ' ALERTA: No se pudo extraer el CUFE del QR para validación cruzada.'

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'datos': {
            'contenido_qr': contenido_qr,
            'qr_datos_parseados': qr_datos if qr_datos else None,
        }
    }

    return resultado
