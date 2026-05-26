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

def test_validar_firma_digital_con_signing_time_valido(xml_firma, monkeypatch):
    """Prueba que la validación sea exitosa al comparar contra la fecha de firma."""
    from unittest.mock import MagicMock
    from datetime import datetime, timezone
    
    # Mockear el certificado
    mock_cert = MagicMock()
    mock_cert.issuer = "CN=Test Issuer"
    mock_cert.subject = "CN=Test Subject"
    mock_cert.not_valid_before_utc = datetime(2023, 1, 1, tzinfo=timezone.utc)
    mock_cert.not_valid_after_utc = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    monkeypatch.setattr(
        "core.python.validators.req_14_firma_digital.extraer_certificado_firma",
        lambda *args, **kwargs: mock_cert
    )
    
    # XML con SigningTime en 2023
    xml_content = """
    <Invoice xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
             xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
             xmlns:xades="http://uri.etsi.org/01903/v1.3.2#">
        <ext:UBLExtensions>
            <ext:UBLExtension>
                <ext:ExtensionContent>
                    <ds:Signature>
                        <ds:SignatureValue>abc123hash</ds:SignatureValue>
                        <ds:KeyInfo>
                            <ds:X509Data>
                                <ds:X509Certificate>
                                    MIIDTjCCAjagAwIBAgIJAJ...
                                </ds:X509Certificate>
                            </ds:X509Data>
                        </ds:KeyInfo>
                    </ds:Signature>
                </ext:ExtensionContent>
            </ext:UBLExtension>
        </ext:UBLExtensions>
        <ext:UBLExtensions>
            <ext:UBLExtension>
                <ext:ExtensionContent>
                    <xades:SigningTime>2023-06-15T10:00:00Z</xades:SigningTime>
                </ext:ExtensionContent>
            </ext:UBLExtension>
        </ext:UBLExtensions>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_firma_digital_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['emisor_certificado'] == "CN=Test Issuer"

def test_validar_firma_digital_con_issue_date_valido(xml_firma, monkeypatch):
    """Prueba fallback a cbc:IssueDate cuando no hay xades:SigningTime."""
    from unittest.mock import MagicMock
    from datetime import datetime, timezone
    
    # Mockear el certificado
    mock_cert = MagicMock()
    mock_cert.issuer = "CN=Test Issuer"
    mock_cert.subject = "CN=Test Subject"
    mock_cert.not_valid_before_utc = datetime(2023, 1, 1, tzinfo=timezone.utc)
    mock_cert.not_valid_after_utc = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    monkeypatch.setattr(
        "core.python.validators.req_14_firma_digital.extraer_certificado_firma",
        lambda *args, **kwargs: mock_cert
    )
    
    # XML sin SigningTime pero con cbc:IssueDate en 2023
    xml_content = """
    <Invoice xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
             xmlns:ds="http://www.w3.org/2000/09/xmldsig#"
             xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
        <cbc:IssueDate>2023-08-20</cbc:IssueDate>
        <cbc:IssueTime>14:30:00-05:00</cbc:IssueTime>
        <ext:UBLExtensions>
            <ext:UBLExtension>
                <ext:ExtensionContent>
                    <ds:Signature>
                        <ds:SignatureValue>abc123hash</ds:SignatureValue>
                        <ds:KeyInfo>
                            <ds:X509Data>
                                <ds:X509Certificate>
                                    MIIDTjCCAjagAwIBAgIJAJ...
                                </ds:X509Certificate>
                            </ds:X509Data>
                        </ds:KeyInfo>
                    </ds:Signature>
                </ext:ExtensionContent>
            </ext:UBLExtension>
        </ext:UBLExtensions>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_firma_digital_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['emisor_certificado'] == "CN=Test Issuer"

