from lxml import etree
import pytest
from core.python.validators.req_12_calidad_tributaria import validar_calidad_tributaria_v1
from metadata.db_metadata import IdTipoError, IdResponsabilidadFiscal

@pytest.fixture
def xml_calidad():
    return """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:AccountingSupplierParty>
            <cac:Party>
                <cac:PartyTaxScheme>
                    <cbc:TaxLevelCode>{emisor}</cbc:TaxLevelCode>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingSupplierParty>
        <cac:AccountingCustomerParty>
            <cac:Party>
                <cac:PartyTaxScheme>
                    <cbc:TaxLevelCode>{adquiriente}</cbc:TaxLevelCode>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingCustomerParty>
    </Invoice>
    """

def test_validar_calidad_tributaria_exito(xml_calidad):
    """Prueba validación exitosa de calidad tributaria (múltiples códigos)."""
    xml_str = xml_calidad.format(
        emisor="O-13; O-23",
        adquiriente="R-99-PN"
    )
    xml = etree.fromstring(xml_str)
    resultado = validar_calidad_tributaria_v1(xml)
    
    assert resultado['valido'] is True
    assert len(resultado['datos']['responsabilidades_emisor']) == 2
    assert resultado['datos']['responsabilidades_emisor'][0]['codigo'] == "O-13"

def test_validar_calidad_tributaria_faltante(xml_calidad):
    """Prueba error cuando no se informa la calidad tributaria del emisor."""
    xml_str = xml_calidad.format(emisor="", adquiriente="R-99-PN")
    xml = etree.fromstring(xml_str)
    resultado = validar_calidad_tributaria_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.calidad_tributaria_faltante
    assert 'No se encontró la calidad tributaria del emisor' in resultado['mensaje']
