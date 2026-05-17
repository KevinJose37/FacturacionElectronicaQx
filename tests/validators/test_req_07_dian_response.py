from lxml import etree
import pytest
from core.python.validators.req_07_factura_validacion_dian import validar_documento_validacion_dian_v1
from metadata.db_metadata import IdTipoError, IdTipoEventoDian

@pytest.fixture
def xml_invoice():
    return etree.fromstring("<Invoice />")

@pytest.fixture
def xml_ar_valido():
    return etree.fromstring(f"""
    <ApplicationResponse xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
                         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cbc:ID>AR-123</cbc:ID>
        <cac:DocumentResponse>
            <cac:Response>
                <cbc:ResponseCode>{IdTipoEventoDian.documento_validado_dian}</cbc:ResponseCode>
                <cbc:Description>Documento validado por la DIAN</cbc:Description>
            </cac:Response>
            <cac:DocumentReference>
                <cbc:UUID>CUFE-VALIDO</cbc:UUID>
            </cac:DocumentReference>
        </cac:DocumentResponse>
    </ApplicationResponse>
    """)

def test_validar_documento_validacion_exito(xml_invoice, xml_ar_valido):
    """Prueba validación exitosa de respuesta DIAN."""
    resultado = validar_documento_validacion_dian_v1(xml_invoice, xml_ar_valido)
    
    assert resultado['valido'] is True
    assert resultado['datos']['codigo_evento'] == IdTipoEventoDian.documento_validado_dian

def test_validar_documento_validacion_rechazado(xml_invoice):
    """Prueba error cuando la respuesta DIAN indica rechazo."""
    xml_ar_rechazo = etree.fromstring(f"""
    <ApplicationResponse xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
                         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:DocumentResponse>
            <cac:Response>
                <cbc:ResponseCode>{IdTipoEventoDian.documento_rechazado_dian}</cbc:ResponseCode>
                <cbc:Description>Documento rechazado por la DIAN</cbc:Description>
            </cac:Response>
        </cac:DocumentResponse>
    </ApplicationResponse>
    """)
    resultado = validar_documento_validacion_dian_v1(xml_invoice, xml_ar_rechazo)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.validacion_dian_fallo
    assert 'no corresponde a "Documento validado por la DIAN"' in resultado['mensaje']

def test_validar_documento_validacion_sin_ar(xml_invoice):
    """Prueba error cuando no se proporciona el XML de respuesta DIAN."""
    resultado = validar_documento_validacion_dian_v1(xml_invoice, None)
    
    assert resultado['valido'] is False
    assert 'No se encontró el XML de validación DIAN' in resultado['mensaje']
