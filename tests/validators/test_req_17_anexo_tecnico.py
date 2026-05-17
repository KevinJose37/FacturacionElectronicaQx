from lxml import etree
import pytest
from core.python.validators.req_17_anexo_tecnico import validar_anexo_tecnico_v1

@pytest.fixture
def xml_ubl():
    """Fixture que retorna un XML con estructura mínima UBL para pruebas."""
    return """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cbc:ID>FAC-1</cbc:ID>
        <cbc:IssueDate>2024-01-01</cbc:IssueDate>
        <cac:AccountingSupplierParty><cac:Party /></cac:AccountingSupplierParty>
        <cac:AccountingCustomerParty><cac:Party /></cac:AccountingCustomerParty>
        <cac:LegalMonetaryTotal><cbc:PayableAmount currencyID="COP">0</cbc:PayableAmount></cac:LegalMonetaryTotal>
        <cac:InvoiceLine><cbc:ID>1</cbc:ID></cac:InvoiceLine>
    </Invoice>
    """

def test_validar_anexo_tecnico_minimo_exito(xml_ubl):
    """Prueba la validación de estructura mínima exitosa."""
    xml = etree.fromstring(xml_ubl)
    resultado = validar_anexo_tecnico_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['metodo_validacion'] == 'estructura_minima'

def test_validar_anexo_tecnico_error_estructura():
    """Prueba error cuando faltan nodos obligatorios."""
    xml = etree.fromstring("<Invoice />")
    resultado = validar_anexo_tecnico_v1(xml)
    
    assert resultado['valido'] is False
    assert 'Faltan nodos' in resultado['mensaje']
