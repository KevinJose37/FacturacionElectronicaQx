from lxml import etree
import pytest
from core.python.validators.req_04_numeracion import validar_numeracion_dian_v1
from metadata.db_metadata import IdTipoError

@pytest.fixture
def xml_base():
    return """
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
             xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
             xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
             xmlns:sts="dian:gov:co:facturaelectronica:Structures-2-1">
        <cbc:ID>{id_factura}</cbc:ID>
        <ext:UBLExtensions>
            <ext:UBLExtension>
                <ext:ExtensionContent>
                    <sts:DianExtensions>
                        <sts:InvoiceControl>
                            <sts:InvoiceAuthorization>{autorizacion}</sts:InvoiceAuthorization>
                            <sts:AuthorizedInvoices>
                                <sts:Prefix>{prefijo}</sts:Prefix>
                                <sts:From>{rango_desde}</sts:From>
                                <sts:To>{rango_hasta}</sts:To>
                            </sts:AuthorizedInvoices>
                        </sts:InvoiceControl>
                    </sts:DianExtensions>
                </ext:ExtensionContent>
            </ext:UBLExtension>
        </ext:UBLExtensions>
    </Invoice>
    """

def test_validar_numeracion_exito(xml_base):
    """Prueba validación exitosa de numeración dentro de rango."""
    xml_str = xml_base.format(
        id_factura="SETT123",
        autorizacion="18760000001",
        prefijo="SETT",
        rango_desde="100",
        rango_hasta="200"
    )
    xml = etree.fromstring(xml_str)
    resultado = validar_numeracion_dian_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['numero_consecutivo'] == 123
    assert resultado['datos']['prefijo'] == "SETT"

def test_validar_numeracion_fuera_de_rango(xml_base):
    """Prueba error cuando el número está fuera del rango autorizado."""
    xml_str = xml_base.format(
        id_factura="SETT250",
        autorizacion="18760000001",
        prefijo="SETT",
        rango_desde="100",
        rango_hasta="200"
    )
    xml = etree.fromstring(xml_str)
    resultado = validar_numeracion_dian_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.numeracion_fuera_de_rango

def test_validar_numeracion_sin_autorizacion(xml_base):
    """Prueba error cuando falta el nodo InvoiceAuthorization."""
    xml_str = xml_base.format(
        id_factura="SETT123",
        autorizacion="",
        prefijo="SETT",
        rango_desde="100",
        rango_hasta="200"
    ).replace("<sts:InvoiceAuthorization></sts:InvoiceAuthorization>", "")
    
    xml = etree.fromstring(xml_str)
    resultado = validar_numeracion_dian_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.numeracion_sin_rango_autorizado

def test_validar_numeracion_sin_prefijo(xml_base):
    """Prueba validación exitosa sin prefijo (numérico puro)."""
    xml_str = xml_base.format(
        id_factura="150",
        autorizacion="18760000001",
        prefijo="",
        rango_desde="100",
        rango_hasta="200"
    )
    xml = etree.fromstring(xml_str)
    resultado = validar_numeracion_dian_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['numero_consecutivo'] == 150
