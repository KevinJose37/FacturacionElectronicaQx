"""Módulo que contiene funciones de validación del anexo técnico UBL de la factura."""

# Standard library imports
import logging
import os

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import validar_estructura_minima_ubl_v1


logger = logging.getLogger(__name__)


def validar_anexo_tecnico_v1(
    xml_invoice: etree._Element | None,
    ruta_xsd: str | None = None,
) -> dict:
    """Valida la factura electrónica contra el anexo técnico UBL 2.1 de la DIAN.
    
    Si se proporciona un XSD, valida contra el esquema formal.
    Si no, realiza una validación de estructura mínima.

    Args:
        xml_invoice: Árbol XML del Invoice a validar.
        ruta_xsd: Ruta al archivo XSD de UBL 2.1 Invoice (opcional).

    Returns:
        Diccionario con:
        - 'valido': bool indicando si cumple con el anexo técnico.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con detalles de la validación.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    }

    resultado_validacion = False
    errores_xsd = []
    metodo_validacion = 'estructura_minima'

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar anexo técnico.'

    elif ruta_xsd and os.path.exists(ruta_xsd):
        # Validación formal contra XSD
        metodo_validacion = 'xsd'
        try:
            with open(ruta_xsd, 'rb') as f:
                schema_doc = etree.parse(f)
                schema = etree.XMLSchema(schema_doc)

            xml_doc = etree.ElementTree(xml_invoice)

            if schema.validate(xml_doc):
                resultado_validacion = True
                mensaje = 'El XML cumple con el esquema XSD UBL 2.1.'
            else:
                errores_xsd = [str(e) for e in schema.error_log]
                mensaje = (
                    'El XML no cumple con el esquema XSD UBL 2.1:\n'
                    + '\n'.join(errores_xsd[:10])
                )

        except Exception as exc:
            mensaje = f'Error al validar contra XSD: {exc}'

    else:
        # Validación de estructura mínima
        resultado, msg = validar_estructura_minima_ubl_v1(
            xml_invoice, NAMESPACES
        )
        resultado_validacion = resultado
        mensaje = msg

        if ruta_xsd and not os.path.exists(ruta_xsd):
            mensaje += f' NOTA: XSD no encontrado en "{ruta_xsd}", se usó validación estructural.'

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'datos': {
            'metodo_validacion': metodo_validacion,
            'errores_xsd': errores_xsd if errores_xsd else None,
        }
    }

    return resultado
