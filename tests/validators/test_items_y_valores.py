from lxml import etree
import pytest
from core.python.validators.req_08_items import validar_lineas_factura_v1
from core.python.validators.req_09_valor import validar_valor_total_v1
from metadata.db_metadata import IdTipoError

@pytest.fixture
def xml_items():
    return """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cbc:LineCountNumeric>1</cbc:LineCountNumeric>
        <cac:InvoiceLine>
            <cbc:ID>1</cbc:ID>
            <cbc:InvoicedQuantity unitCode="94">10.00</cbc:InvoicedQuantity>
            <cbc:LineExtensionAmount currencyID="COP">100000.00</cbc:LineExtensionAmount>
            <cac:Item>
                <cbc:Description>Servicio de Consultoría</cbc:Description>
                <cac:StandardItemIdentification>
                    <cbc:ID>SERV-001</cbc:ID>
                </cac:StandardItemIdentification>
            </cac:Item>
            <cac:Price>
                <cbc:PriceAmount currencyID="COP">10000.00</cbc:PriceAmount>
            </cac:Price>
        </cac:InvoiceLine>
    </Invoice>
    """

def test_validar_lineas_exito(xml_items):
    """Prueba validación exitosa de líneas de factura."""
    xml = etree.fromstring(xml_items)
    resultado = validar_lineas_factura_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['total_lineas'] == 1
    assert resultado['datos']['lineas'][0]['descripcion'] == 'Servicio de Consultoría'

def test_validar_lineas_error_descripcion(xml_items):
    """Prueba error cuando una línea no tiene descripción."""
    xml_str = xml_items.replace("<cbc:Description>Servicio de Consultoría</cbc:Description>", "<cbc:Description></cbc:Description>")
    xml = etree.fromstring(xml_str)
    resultado = validar_lineas_factura_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.linea_sin_descripcion

def test_validar_valor_total_exito():
    """Prueba validación exitosa del valor total (suma cuadra)."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:TaxTotal>
            <cbc:TaxAmount currencyID="COP">19000.00</cbc:TaxAmount>
        </cac:TaxTotal>
        <cac:LegalMonetaryTotal>
            <cbc:LineExtensionAmount currencyID="COP">100000.00</cbc:LineExtensionAmount>
            <cbc:PayableAmount currencyID="COP">119000.00</cbc:PayableAmount>
        </cac:LegalMonetaryTotal>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_valor_total_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['valor_a_pagar'] == "119000.00"

def test_validar_valor_total_error_diferencia():
    """Prueba error cuando la suma de bruto + impuestos no coincide con el total."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:TaxTotal>
            <cbc:TaxAmount currencyID="COP">19000.00</cbc:TaxAmount>
        </cac:TaxTotal>
        <cac:LegalMonetaryTotal>
            <cbc:LineExtensionAmount currencyID="COP">100000.00</cbc:LineExtensionAmount>
            <cbc:PayableAmount currencyID="COP">200000.00</cbc:PayableAmount>
        </cac:LegalMonetaryTotal>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_valor_total_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.valor_total_inconsistente
