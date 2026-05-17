from lxml import etree
import pytest
from core.python.validators.req_16_qr_code import validar_qr_code_v1

@pytest.fixture
def xml_qr():
    """Fixture que retorna un XML con nodo de QR para pruebas."""
    return """
    <Invoice xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
             xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1">
        <ext:UBLExtensions>
            <ext:UBLExtension>
                <ext:ExtensionContent>
                    <sts:DianExtensions>
                        <sts:QRCode>https://catalogo.dian.gov.co/document/searchqc?DocumentKey=CUFE_TEST&amp;NumFac=123</sts:QRCode>
                    </sts:DianExtensions>
                </ext:ExtensionContent>
            </ext:UBLExtension>
        </ext:UBLExtensions>
    </Invoice>
    """

def test_validar_qr_exito(xml_qr):
    """Prueba validación exitosa de QR con CUFE coincidente."""
    xml = etree.fromstring(xml_qr)
    resultado = validar_qr_code_v1(xml, cufe="CUFE_TEST")
    
    assert resultado['valido'] is True
    assert resultado['datos']['qr_datos_parseados']['DocumentKey'] == 'CUFE_TEST'

def test_validar_qr_error_cufe(xml_qr):
    """Prueba advertencia cuando el CUFE no coincide."""
    xml = etree.fromstring(xml_qr)
    resultado = validar_qr_code_v1(xml, cufe="OTRO_CUFE")
    
    assert resultado['valido'] is True # Aún es válido porque el QR está presente
    assert 'CUFE no coincide' in resultado['mensaje']

def test_validar_qr_sin_nodo():
    """Prueba error cuando no existe el nodo QR."""
    xml = etree.fromstring("<Invoice />")
    resultado = validar_qr_code_v1(xml)
    
    assert resultado['valido'] is False
    assert 'No se encontró el código QR' in resultado['mensaje']
