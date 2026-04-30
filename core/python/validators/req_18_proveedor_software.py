"""Módulo que contiene funciones para validar la información del fabricante del software y
 proveedor tecnológico"""

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import extraer_texto_xpath


def validar_software_y_proveedor_v1(xml_factura: etree._Element) -> bool:
    """Valida la información del fabricante del software y proveedor tecnológico
    según la resolución 000165 de 2023.

    Verifica:
    - presencia de sts:SoftwareProvider
    - presencia de NIT (ProviderID)
    - presencia de razón social (ProviderName)
    - presencia de SoftwareID

    Args:
        xml_factura: Elemento raíz del XML de la factura (Invoice).

    Returns:
        True si la información del software/proveedor es válida, False en caso contrario.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
    }

    resultado_validacion = False

    proveedor_nit = extraer_texto_xpath(
        xml_factura,
        './/sts:SoftwareProvider/sts:ProviderID',
        NAMESPACES,
    )

    proveedor_nombre = extraer_texto_xpath(
        xml_factura,
        './/sts:SoftwareProvider/sts:ProviderName',
        NAMESPACES,
    )

    software_id = extraer_texto_xpath(
        xml_factura,
        './/sts:SoftwareID',
        NAMESPACES,
    )

    if not proveedor_nit:
        mensaje = (
            'No se informó el NIT del fabricante del software o proveedor tecnológico '
            '(sts:SoftwareProvider/sts:ProviderID).'
        )
    elif not proveedor_nombre:
        mensaje = (
            'No se informó la razón social del fabricante del software o proveedor '
            'tecnológico (sts:SoftwareProvider/sts:ProviderName).'
        )
    elif not software_id:
        mensaje = (
            'No se informó el identificador del software (sts:SoftwareID).'
        )
    else:
        resultado_validacion = True
        mensaje = (
            'Se informó correctamente el fabricante del software/proveedor tecnológico. '
            f'NIT: {proveedor_nit}, Nombre: {proveedor_nombre}, '
            f'SoftwareID: {software_id}.'
        )

    enviar_log_validacion(mensaje)

    return resultado_validacion
