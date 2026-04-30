"""Módulo que contiene las versiones de la validación de la información del
adquiriente."""

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import calcular_dv_nit_v1
from core.python.utils.validacion import validar_datos_persona


def validar_adquiriente_v1(xml_raw: etree._Element) -> bool:
    """Valida los datos del adquiriente (nombre/razón social y NIT) según la resolución
     000165 de 2023.
     
    Args:
        xml_raw: Elemento raíz del XML de la factura electrónica.

    Reglas:
    - Siempre requiere nombre
    - Si schemeName == 31 (NIT), se valida:
        - Presencia de NIT
        - Longitud
        - Dígito de verificación

    Retorna:
        True si el adquiriente cumple con los requisitos, False en caso contrario.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

    XPATH_BASE = './cac:AccountingCustomerParty/cac:Party'

    nodos_nombre = xml_raw.xpath(
        XPATH_BASE + '/cac:PartyName/cbc:Name', namespaces=NAMESPACES
    )

    if not nodos_nombre:
        nodos_nombre = xml_raw.xpath(
            XPATH_BASE + '/cac:PartyLegalEntity/cbc:RegistrationName',
            namespaces=NAMESPACES
        )

    nombre = (nodos_nombre[0].text or '').strip() if nodos_nombre else None

    nodos_nit = xml_raw.xpath(
        XPATH_BASE + '/cac:PartyTaxScheme/cbc:CompanyID', namespaces=NAMESPACES
    )

    nodo_nit = nodos_nit[0] if nodos_nit else None
    nit = (nodo_nit.text or '').strip() if nodo_nit else None
    scheme_name = nodo_nit.get('schemeName') if nodo_nit else None
    dv_xml = nodo_nit.get('schemeID') if nodo_nit else None

    validacion = validar_datos_persona(
        nombre, nit, scheme_name, dv_xml
    )
    
    enviar_log_validacion(validacion['mensaje'])
    
    resultado_validacion = validacion['resultado']

    return resultado_validacion
