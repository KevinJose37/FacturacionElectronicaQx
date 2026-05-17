from lxml import etree
import pytest
from core.python.validators.req_14_firma_digital import validar_firma_digital_v1

@pytest.fixture
def xml_firma():
    """Fixture que retorna un XML con nodo de firma para pruebas."""
    return """
    <Invoice xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
             xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
        <ext:UBLExtensions>
            <ext:UBLExtension>
                <ext:ExtensionContent>
                    <ds:Signature>
                        <ds:SignatureValue>abc123hash</ds:SignatureValue>
                        <ds:KeyInfo>
                            <ds:X509Data>
                                <ds:X509Certificate>
                                    MIIDTjCCAjagAwIBAgIJAJ... (Certificado Base64 omitido)
                                </ds:X509Certificate>
                            </ds:X509Data>
                        </ds:KeyInfo>
                    </ds:Signature>
                </ext:ExtensionContent>
            </ext:UBLExtension>
        </ext:UBLExtensions>
    </Invoice>
    """

def test_validar_firma_digital_sin_nodo():
    """Prueba error cuando no existe el nodo de firma."""
    xml = etree.fromstring("<Invoice />")
    resultado = validar_firma_digital_v1(xml)
    
    assert resultado['valido'] is False
    assert 'No se encontró la firma digital' in resultado['mensaje']

# Nota: REQ-14 requiere Mocks para validación criptográfica real o certificados reales.
# Aquí probamos la detección del nodo.
