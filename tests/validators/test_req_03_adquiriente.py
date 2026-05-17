from lxml import etree
import pytest
from core.python.validators.req_03_adquiriente import validar_adquiriente_v1
from metadata.db_metadata import IdTipoError

@pytest.fixture
def namespaces():
    return {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2'
    }

def test_validar_adquiriente_v1_exito_nit(namespaces):
    """Prueba validación exitosa de adquiriente con NIT y DV correcto."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:AccountingCustomerParty>
            <cac:Party>
                <cac:PartyLegalEntity>
                    <cbc:RegistrationName>COMPRADOR SAS</cbc:RegistrationName>
                </cac:PartyLegalEntity>
                <cac:PartyTaxScheme>
                    <cbc:CompanyID schemeName="31" schemeID="4">800197268</cbc:CompanyID>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingCustomerParty>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_adquiriente_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['numero_documento'] == '800197268'
    assert resultado['datos']['digito_verificador'] == '4'

def test_validar_adquiriente_v1_error_dv(namespaces):
    """Prueba error cuando el DV del adquiriente es incorrecto."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:AccountingCustomerParty>
            <cac:Party>
                <cac:PartyLegalEntity>
                    <cbc:RegistrationName>COMPRADOR SAS</cbc:RegistrationName>
                </cac:PartyLegalEntity>
                <cac:PartyTaxScheme>
                    <cbc:CompanyID schemeName="31" schemeID="0">800197268</cbc:CompanyID>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingCustomerParty>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_adquiriente_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.adquiriente_dv_invalido

def test_validar_adquiriente_v1_consumidor_final(namespaces):
    """Prueba validación de consumidor final (NIT 222222222 sin DV en XML)."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:AccountingCustomerParty>
            <cac:Party>
                <cac:PartyName>
                    <cbc:Name>CONSUMIDOR FINAL</cbc:Name>
                </cac:PartyName>
                <cac:PartyTaxScheme>
                    <cbc:CompanyID schemeName="13">222222222</cbc:CompanyID>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingCustomerParty>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_adquiriente_v1(xml)
    
    # Tipo 13 (Cédula) no requiere DV
    assert resultado['valido'] is True
    assert resultado['datos']['numero_documento'] == '222222222'
