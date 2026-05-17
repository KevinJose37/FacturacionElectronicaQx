from lxml import etree
import pytest
from core.python.validators.req_10_forma_pago import validar_forma_pago_v1
from core.python.validators.req_11_medio_pago import validar_medio_pago_v1
from metadata.db_metadata import IdTipoError, IdFormaPago, IdMedioPago

@pytest.fixture
def xml_pago():
    return """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:PaymentMeans>
            <cbc:ID>{forma}</cbc:ID>
            <cbc:PaymentMeansCode>{medio}</cbc:PaymentMeansCode>
            {vencimiento}
        </cac:PaymentMeans>
    </Invoice>
    """

def test_validar_forma_pago_contado(xml_pago):
    """Prueba validación exitosa de forma de pago contado."""
    xml_str = xml_pago.format(forma=IdFormaPago.contado, medio="10", vencimiento="")
    xml = etree.fromstring(xml_str)
    resultado = validar_forma_pago_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['codigo_forma_pago'] == IdFormaPago.contado

def test_validar_forma_pago_credito_vencimiento(xml_pago):
    """Prueba validación de crédito con fecha de vencimiento."""
    xml_str = xml_pago.format(
        forma=IdFormaPago.credito, 
        medio="30", 
        vencimiento="<cbc:PaymentDueDate>2024-02-01</cbc:PaymentDueDate>"
    )
    xml = etree.fromstring(xml_str)
    resultado = validar_forma_pago_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['fecha_vencimiento'] == "2024-02-01"

def test_validar_medio_pago_contado_exito(xml_pago):
    """Prueba validación exitosa de medio de pago para contado."""
    xml_str = xml_pago.format(forma=IdFormaPago.contado, medio=IdMedioPago.efectivo, vencimiento="")
    xml = etree.fromstring(xml_str)
    resultado = validar_medio_pago_v1(xml, codigo_forma_pago=IdFormaPago.contado)
    
    assert resultado['valido'] is True
    assert resultado['datos']['codigo_medio_pago'] == IdMedioPago.efectivo

def test_validar_medio_pago_contado_faltante(xml_pago):
    """Prueba error cuando falta el medio de pago en una factura de contado."""
    xml_str = xml_pago.format(forma=IdFormaPago.contado, medio="", vencimiento="")
    xml_str = xml_str.replace("<cbc:PaymentMeansCode></cbc:PaymentMeansCode>", "")
    xml = etree.fromstring(xml_str)
    resultado = validar_medio_pago_v1(xml, codigo_forma_pago=IdFormaPago.contado)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.medio_pago_invalido
    assert 'Es obligatorio para pagos de contado' in resultado['mensaje']
