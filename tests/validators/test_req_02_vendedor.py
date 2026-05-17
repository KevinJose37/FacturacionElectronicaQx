from lxml import etree
import pytest
from core.python.validators.req_02_vendedor import validar_emisor_v1
from metadata.db_metadata import IdTipoError

@pytest.fixture
def namespaces():
    return {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

def test_validar_emisor_v1_exito_nit(namespaces):
    """Prueba validación exitosa de emisor con NIT y DV correcto."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:AccountingSupplierParty>
            <cac:Party>
                <cac:PartyName>
                    <cbc:Name>MI EMPRESA SAS</cbc:Name>
                </cac:PartyName>
                <cac:PartyTaxScheme>
                    <cbc:CompanyID schemeName="31" schemeID="3">900123456</cbc:CompanyID>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingSupplierParty>
    </Invoice>
    """
    # Nota: El DV de 900123456 es 3 (calculado: (9*71 + 0*67 + 0*59 + 1*53 + 2*47 + 3*43 + 4*41 + 5*37 + 6*29)%11 ...)
    # Vamos a usar uno conocido: 800197268 -> DV 4
    xml_content = xml_content.replace("900123456", "800197268").replace('schemeID="3"', 'schemeID="4"')
    
    xml = etree.fromstring(xml_content)
    resultado = validar_emisor_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['numero_documento'] == '800197268'
    assert resultado['datos']['digito_verificador'] == '4'

def test_validar_emisor_v1_error_dv(namespaces):
    """Prueba error cuando el DV en el XML no coincide con el calculado."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:AccountingSupplierParty>
            <cac:Party>
                <cac:PartyLegalEntity>
                    <cbc:RegistrationName>EMPRESA TEST</cbc:RegistrationName>
                </cac:PartyLegalEntity>
                <cac:PartyTaxScheme>
                    <cbc:CompanyID schemeName="31" schemeID="9">800197268</cbc:CompanyID>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingSupplierParty>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_emisor_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.emisor_dv_invalido
    assert 'DV incorrecto' in resultado['mensaje']

def test_validar_emisor_v1_sin_nombre(namespaces):
    """Prueba error cuando no hay nombre ni razón social."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:AccountingSupplierParty>
            <cac:Party>
                <cac:PartyTaxScheme>
                    <cbc:CompanyID schemeName="31" schemeID="4">800197268</cbc:CompanyID>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingSupplierParty>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_emisor_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.emisor_sin_nombre

def test_validar_emisor_v1_cedula_extranjeria(namespaces):
    """Prueba validación con otro tipo de documento (Cédula Extranjería - 22) que no requiere DV."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:AccountingSupplierParty>
            <cac:Party>
                <cac:PartyName>
                    <cbc:Name>JUAN EXTRANJERO</cbc:Name>
                </cac:PartyName>
                <cac:PartyTaxScheme>
                    <cbc:CompanyID schemeName="22">E12345678</cbc:CompanyID>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingSupplierParty>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_emisor_v1(xml)
    
    # Según lógica en validacion.py: "Documento que no requiere DV: válido si tiene nombre y número"
    assert resultado['valido'] is True
    assert resultado['datos']['scheme_name'] == '22'
