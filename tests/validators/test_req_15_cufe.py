import hashlib
from lxml import etree
import pytest
from core.python.validators.req_15_cufe import validar_cufe_v1
from metadata.db_metadata import IdTipoError

@pytest.fixture
def xml_cufe():
    return """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
             xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
             xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1">
        <cbc:ID>FAC-123</cbc:ID>
        <cbc:IssueDate>2024-01-01</cbc:IssueDate>
        <cbc:IssueTime>10:00:00-05:00</cbc:IssueTime>
        <cbc:UUID schemeName="CUFE">{cufe}</cbc:UUID>
        <cbc:ProfileExecutionID>1</cbc:ProfileExecutionID>
        <cac:AccountingCustomerParty>
            <cac:Party>
                <cac:PartyTaxScheme>
                    <cbc:CompanyID>900123456</cbc:CompanyID>
                </cac:PartyTaxScheme>
            </cac:Party>
        </cac:AccountingCustomerParty>
        <cac:LegalMonetaryTotal>
            <cbc:PayableAmount currencyID="COP">119000.00</cbc:PayableAmount>
        </cac:LegalMonetaryTotal>
        <ext:UBLExtensions>
            <ext:UBLExtension>
                <ext:ExtensionContent>
                    <sts:DianExtensions>
                        <sts:SoftwareSecurityCode>CLAVE_TECNICA</sts:SoftwareSecurityCode>
                    </sts:DianExtensions>
                </ext:ExtensionContent>
            </ext:UBLExtension>
        </ext:UBLExtensions>
    </Invoice>
    """

def test_validar_cufe_v1_exito(xml_cufe):
    """Prueba validación exitosa del CUFE calculando el hash esperado dinámicamente."""
    # La cadena base construida por el sistema para el XML del fixture es:
    # ID + IssueDate + IssueTime + PayableAmount + Impuestos(01-06) + NIT_Adq + SoftwareSecurityCode + ProfileExecutionID
    # FAC-123 + 2024-01-01 + 10:00:00-05:00 + 119000.00 + 010.00020.00030.00040.00050.00060.00 + 900123456 + CLAVE_TECNICA + 1
    
    cadena_base = "FAC-1232024-01-0110:00:00-05:00119000.00010.00020.00030.00040.00050.00060.00900123456CLAVE_TECNICA1"
    cufe_calculado = hashlib.sha384(cadena_base.encode('utf-8')).hexdigest()
    
    xml_str = xml_cufe.format(cufe=cufe_calculado)
    xml = etree.fromstring(xml_str)
    resultado = validar_cufe_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['cufe_coincide'] is True

def test_validar_cufe_v1_sin_uuid(xml_cufe):
    """Prueba error cuando falta el CUFE en el XML."""
    xml_str = xml_cufe.format(cufe="")
    xml_str = xml_str.replace('<cbc:UUID schemeName="CUFE"></cbc:UUID>', "")
    xml = etree.fromstring(xml_str)
    resultado = validar_cufe_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.cufe_invalido
    assert 'No se encontró el CUFE' in resultado['mensaje']
