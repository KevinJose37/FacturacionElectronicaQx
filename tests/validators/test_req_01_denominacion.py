from lxml import etree
import pytest
from core.python.validators.req_01_denominacion import validar_denominacion_v1
from metadata.db_metadata import IdTipoError

@pytest.fixture
def xml_denominacion():
    """Fixture que retorna una función para generar XML de denominación."""
    def _generar(profile_text: str = 'Factura Electrónica de Venta', type_code: str = '01'):
        xml_content = f"""
        <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
            <cbc:ProfileID>{profile_text}</cbc:ProfileID>
            <cbc:InvoiceTypeCode>{type_code}</cbc:InvoiceTypeCode>
        </Invoice>
        """
        return etree.fromstring(xml_content)
    return _generar

def test_validar_denominacion_v1_exito(xml_denominacion):
    """Prueba validación exitosa con ProfileID y InvoiceTypeCode correctos."""
    xml = xml_denominacion()
    resultado = validar_denominacion_v1(xml)
    
    assert resultado['valido'] is True
    assert 'Denominación correcta' in resultado['mensaje']
    assert resultado['datos']['codigo_tipo_documento'] == '01'

def test_validar_denominacion_v1_case_insensitive(xml_denominacion):
    """Prueba que la validación sea tolerante a mayúsculas/minúsculas."""
    xml = xml_denominacion(profile_text='factura electrónica de venta')
    resultado = validar_denominacion_v1(xml)
    
    assert resultado['valido'] is True

def test_validar_denominacion_v1_erronea(xml_denominacion):
    """Prueba error cuando el ProfileID no contiene la cadena requerida."""
    xml = xml_denominacion(profile_text='Documento Equivalente')
    resultado = validar_denominacion_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.error_procesamiento_general
    assert 'Denominación incorrecta' in resultado['mensaje']

def test_validar_denominacion_v1_sin_profile():
    """Prueba error cuando no existe el nodo ProfileID."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
        <cbc:InvoiceTypeCode>01</cbc:InvoiceTypeCode>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_denominacion_v1(xml)
    
    assert resultado['valido'] is False
    assert 'No se encontró el nodo cbc:ProfileID' in resultado['mensaje']

def test_validar_denominacion_v1_tipo_documento_invalido(xml_denominacion):
    """Prueba error cuando el código de tipo de documento no es de factura."""
    xml = xml_denominacion(type_code='91')
    resultado = validar_denominacion_v1(xml)
    
    assert resultado['valido'] is False
    assert 'no corresponde a una factura electrónica válida' in resultado['mensaje']

def test_validar_denominacion_v1_sin_type_code():
    """Prueba que si no hay TypeCode pero el Profile es correcto, sea válido (según lógica actual)."""
    xml_content = """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
        <cbc:ProfileID>Factura Electrónica de Venta</cbc:ProfileID>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_denominacion_v1(xml)
    
    assert resultado['valido'] is True
    assert 'no se encontró el código de tipo de documento' in resultado['mensaje']
