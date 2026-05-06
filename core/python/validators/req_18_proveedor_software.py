"""Módulo que contiene funciones de validación del proveedor de software
 tecnológico de la factura."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree
from metadata.db_metadata import IdTipoError

# Local application imports
from core.python.utils.validacion import extraer_texto_xpath


logger = logging.getLogger(__name__)

def validar_proveedor_software_v1(xml_invoice: etree._Element | None) -> dict:
    """Valida la información del proveedor de software tecnológico de la factura
     electrónica según la resolución 000165 de 2023.

    Args:
        xml_invoice: Árbol XML del Invoice a validar.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si los datos del proveedor son válidos.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con NIT, software ID, security code y PIN del proveedor.
    """
    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
        'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
        'sts': 'dian:gov:co:facturaelectronica:Structures-2-1',
    }

    resultado_validacion = False
    nit_proveedor = None
    nombre_proveedor = None
    id_software = None
    security_code = None
    pin = None

    if xml_invoice is None:
        mensaje = 'No se encontró el XML Invoice para validar proveedor de software.'

    else:
        # Extraer datos del proveedor desde SoftwareProvider
        nit_proveedor = extraer_texto_xpath(
            xml_invoice,
            './/sts:SoftwareProvider/sts:ProviderID',
            NAMESPACES
        )

        nombre_proveedor = extraer_texto_xpath(
            xml_invoice,
            './/sts:SoftwareProvider/sts:ProviderID',
            NAMESPACES
        )
        # Intentar obtener el schemeName del ProviderID para el nombre
        nodo_provider_id = xml_invoice.xpath(
            './/sts:SoftwareProvider/sts:ProviderID', namespaces=NAMESPACES
        )
        if nodo_provider_id:
            nombre_proveedor = nodo_provider_id[0].get('schemeName') or nit_proveedor

        # Extraer ID del software
        id_software = extraer_texto_xpath(
            xml_invoice,
            './/sts:SoftwareProvider/sts:SoftwareID',
            NAMESPACES
        )

        # Extraer el código de seguridad del software
        security_code = extraer_texto_xpath(
            xml_invoice,
            './/sts:SoftwareSecurityCode',
            NAMESPACES
        )

        # Extraer PIN (si existe)
        pin = extraer_texto_xpath(
            xml_invoice,
            './/sts:AuthorizationProvider/sts:AuthorizationProviderID',
            NAMESPACES
        )

        if not nit_proveedor:
            mensaje = (
                'No se encontró el NIT del proveedor tecnológico '
                '(sts:ProviderID).'
            )

        elif not id_software:
            mensaje = (
                f'Proveedor NIT {nit_proveedor} encontrado, '
                f'pero sin ID de software (sts:SoftwareID).'
            )

        else:
            resultado_validacion = True
            mensaje = (
                f'Proveedor de software válido: NIT {nit_proveedor}, '
                f'Software ID {id_software}.'
            )

    logger.debug(mensaje)

    resultado = {
        'valido': resultado_validacion,
        'mensaje': mensaje,
        'id_error': IdTipoError.software_proveedor_faltante if not resultado_validacion else None,
        'datos': {
            'nit_proveedor': nit_proveedor,
            'nombre_proveedor': nombre_proveedor,
            'id_software': id_software,
            'security_code': security_code,
            'pin': pin,
        }
    }

    return resultado
