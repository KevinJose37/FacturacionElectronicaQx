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

# NIT de los proveedores tecnológicos autorizados por la DIAN.
# Corresponden a la tabla PROVEEDOR_TECNOLOGICO.
NITS_PROVEEDORES_AUTORIZADOS = {
    '901020203', '830099008', '901037591', '900464969', '900965992',
    '900372288', '900297700', '901137226', '901066054', '830005677',
    '900011395', '901121154', '900665411', '890930534', '800096812',
    '890321151', '805012299', '830057860', '800150249', '900646251',
    '901180226', '900457033', '900949812', '901223648', '900918004',
    '860028581', '860028580', '800088155', '805018674', '900680995',
    '900957899', '901081604', '900984424', '900306823', '900273836',
    '900896085', '900875062', '901187615', '900399741', '890901481',
    '900204272', '900730535', '900133732', '900711544', '901014886',
    '811021438', '890941901', '901183470', '900556261', '900123011',
    '900738794', '860502327', '860515402', '800255858', '900176162',
    '901285179', '830074854', '900521653', '830003840', '900032774',
    '830135010', '900749874', '800101428', '830502641', '900013664',
    '890923937', '830096620', '900299474', '800026212', '900606963',
    '900035507', '901356496', '900508908', '830048145', '901098244',
    '890319193', '830084433', '900379787', '900364710', '900395252',
    '900559088', '901361537', '800157786', '900083058', '830020470',
    '900390126', '900423948', '800182856', '900032159', '901034990',
    '811026198', '900534356',
}


def validar_proveedor_software_v1(xml_invoice: etree._Element | None) -> dict:
    """Valida la información del proveedor de software tecnológico de la factura
     electrónica según la resolución 000165 de 2023.

    Args:
        xml_invoice: Árbol XML del Invoice a validar.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si los datos del proveedor son válidos.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con NIT, software ID, security code, PIN y
            es_autorizado del proveedor.
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
    es_autorizado = False

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
            es_autorizado = nit_proveedor in NITS_PROVEEDORES_AUTORIZADOS

            if es_autorizado:
                mensaje = (
                    f'Proveedor de software válido y autorizado DIAN: '
                    f'NIT {nit_proveedor}, Software ID {id_software}.'
                )
            else:
                mensaje = (
                    f'Proveedor de software válido: NIT {nit_proveedor}, '
                    f'Software ID {id_software}. '
                    f'ALERTA: NIT no figura en el registro de proveedores '
                    f'tecnológicos autorizados DIAN.'
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
            'es_autorizado': es_autorizado,
        }
    }

    return resultado
