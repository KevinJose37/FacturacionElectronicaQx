from lxml import etree
import pytest
from core.python.validators.req_18_proveedor_software import validar_proveedor_software_v1

@pytest.fixture
def xml_software():
    """Fixture que retorna un XML con datos del proveedor de software."""
    return """
    <Invoice xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
             xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1">
        <ext:UBLExtensions>
            <ext:UBLExtension>
                <ext:ExtensionContent>
                    <sts:DianExtensions>
                        <sts:SoftwareProvider>
                            <sts:ProviderID schemeName="Software SA">901020203</sts:ProviderID>
                            <sts:SoftwareID>ID-SOFTWARE-123</sts:SoftwareID>
                        </sts:SoftwareProvider>
                        <sts:SoftwareSecurityCode>SEC-123</sts:SoftwareSecurityCode>
                    </sts:DianExtensions>
                </ext:ExtensionContent>
            </ext:UBLExtension>
        </ext:UBLExtensions>
    </Invoice>
    """

def test_validar_proveedor_software_exito_autorizado(xml_software):
    """Prueba validación exitosa de un proveedor autorizado DIAN."""
    xml = etree.fromstring(xml_software)
    resultado = validar_proveedor_software_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['es_autorizado'] is True
    assert resultado['datos']['nit_proveedor'] == '901020203'

def test_validar_proveedor_software_no_autorizado(xml_software):
    """Prueba validación exitosa pero con alerta de no autorizado."""
    xml_str = xml_software.replace('901020203', '123456789')
    xml = etree.fromstring(xml_str)
    resultado = validar_proveedor_software_v1(xml)
    
    assert resultado['valido'] is True # Sigue siendo válido formalmente
    assert resultado['datos']['es_autorizado'] is False
    assert 'ALERTA: NIT no figura' in resultado['mensaje']

def test_validar_proveedor_software_sin_id(xml_software):
    """Prueba error cuando falta el SoftwareID."""
    xml_str = xml_software.replace('<sts:SoftwareID>ID-SOFTWARE-123</sts:SoftwareID>', '')
    xml = etree.fromstring(xml_str)
    resultado = validar_proveedor_software_v1(xml)
    
    assert resultado['valido'] is False
    assert 'sin ID de software' in resultado['mensaje']
