"""Módulo que contiene las versiones de la validación de la información del
adquiriente."""

# Standard library imports
import logging

# Third-party imports
from lxml import etree

# Local application imports
from core.python.utils.validacion import validar_datos_persona

logger = logging.getLogger(__name__)


def validar_adquiriente_v1(xml_raw: etree._Element) -> dict:
    """Valida los datos del adquiriente (nombre/razón social y NIT) según la resolución
     000165 de 2023.
     
    Args:
        xml_raw: Elemento raíz del XML de la factura electrónica.

    Returns:
        Diccionario con:
        - 'valido': bool indicando si el adquiriente cumple con los requisitos.
        - 'mensaje': str con la descripción del resultado.
        - 'datos': dict con nombre, nit, dv, scheme_name, correo, telefono.
    """

    NAMESPACES = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

    XPATH_BASE = './cac:AccountingCustomerParty/cac:Party'

    # Extraer nombre: primero PartyLegalEntity (más confiable), luego PartyName, luego PartyTaxScheme
    nodos_razon_social = xml_raw.xpath(
        XPATH_BASE + '/cac:PartyLegalEntity/cbc:RegistrationName',
        namespaces=NAMESPACES
    )
    nodos_nombre_comercial = xml_raw.xpath(
        XPATH_BASE + '/cac:PartyName/cbc:Name', namespaces=NAMESPACES
    )
    nodos_razon_social_tax = xml_raw.xpath(
        XPATH_BASE + '/cac:PartyTaxScheme/cbc:RegistrationName',
        namespaces=NAMESPACES
    )

    razon_social = (
        (nodos_razon_social[0].text or '').strip()
        if nodos_razon_social else None
    )
    nombre_comercial = (
        (nodos_nombre_comercial[0].text or '').strip()
        if nodos_nombre_comercial else None
    )
    razon_social_tax = (
        (nodos_razon_social_tax[0].text or '').strip()
        if nodos_razon_social_tax else None
    )
    nombre = razon_social or nombre_comercial or razon_social_tax

    # Extraer NIT y atributos
    nodos_nit = xml_raw.xpath(
        XPATH_BASE + '/cac:PartyTaxScheme/cbc:CompanyID', namespaces=NAMESPACES
    )

    nodo_nit = nodos_nit[0] if nodos_nit else None
    nit = (nodo_nit.text or '').strip() if nodo_nit is not None else None
    scheme_name = nodo_nit.get('schemeName') if nodo_nit is not None else None
    dv_xml = nodo_nit.get('schemeID') if nodo_nit is not None else None

    # Extraer contacto
    nodo_correo = xml_raw.xpath(
        XPATH_BASE + '/cac:Contact/cbc:ElectronicMail', namespaces=NAMESPACES
    )
    nodo_telefono = xml_raw.xpath(
        XPATH_BASE + '/cac:Contact/cbc:Telephone', namespaces=NAMESPACES
    )
    correo = (nodo_correo[0].text or '').strip() if nodo_correo else None
    telefono = (nodo_telefono[0].text or '').strip() if nodo_telefono else None

    validacion = validar_datos_persona(nombre, nit, scheme_name, dv_xml, rol='adquiriente')

    if validacion['resultado']:
        validacion['mensaje'] = 'Datos del adquiriente válidos.'

    logger.debug(validacion['mensaje'])

    resultado = {
        'valido': validacion['resultado'],
        'mensaje': validacion['mensaje'],
        'datos': {
            'razon_social': razon_social or razon_social_tax or nombre,
            'nombre_comercial': nombre_comercial,
            'numero_documento': nit,
            'digito_verificador': dv_xml,
            'scheme_name': scheme_name,
            'correo_contacto': correo,
            'telefono_contacto': telefono,
        }
    }

    if not validacion['resultado']:
        resultado['id_error'] = validacion.get('id_error')

    return resultado
