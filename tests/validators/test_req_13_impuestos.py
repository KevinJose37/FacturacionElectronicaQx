from lxml import etree
import pytest
from core.python.validators.req_13_impuestos import validar_impuestos_v1

@pytest.fixture
def xml_impuestos():
    """Fixture que retorna un XML con impuestos para pruebas."""
    return """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:TaxTotal>
            <cbc:TaxAmount currencyID="COP">19000.00</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount currencyID="COP">100000.00</cbc:TaxableAmount>
                <cbc:TaxAmount currencyID="COP">19000.00</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:Percent>19.00</cbc:Percent>
                    <cac:TaxScheme>
                        <cbc:ID>01</cbc:ID>
                        <cbc:Name>IVA</cbc:Name>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
    </Invoice>
    """

def test_validar_impuestos_exito(xml_impuestos):
    """Prueba la validación exitosa de impuestos."""
    xml = etree.fromstring(xml_impuestos)
    resultado = validar_impuestos_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['total_impuestos'] == '19000.00'
    assert len(resultado['datos']['impuestos']) == 1
    assert resultado['datos']['impuestos'][0]['codigo_impuesto'] == '01'

def test_validar_impuestos_vacio():
    """Prueba que una factura sin impuestos sea válida (exenta)."""
    xml = etree.fromstring("<Invoice />")
    resultado = validar_impuestos_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['total_impuestos'] == '0.00'

def test_validar_impuestos_error_valor():
    """Prueba error cuando el valor del impuesto no es numérico."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:TaxTotal>
            <cac:TaxSubtotal>
                <cbc:TaxAmount>INVALIDO</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cac:TaxScheme><cbc:ID>01</cbc:ID></cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_impuestos_v1(xml)
    
    assert resultado['valido'] is False
    assert 'no numérico' in resultado['mensaje']
