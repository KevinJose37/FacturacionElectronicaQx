from lxml import etree
import pytest
from datetime import datetime, timedelta, timezone
from core.python.validators.req_05_fecha_generacion import validar_fecha_generacion_v1
from core.python.validators.req_06_fecha_validacion import validar_fecha_validacion_dian_v1
from metadata.db_metadata import IdTipoError

def test_validar_fecha_generacion_exito():
    """Prueba validación exitosa de fecha de generación (pasada)."""
    ayer = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    xml_content = f"""
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
        <cbc:IssueDate>{ayer}</cbc:IssueDate>
        <cbc:IssueTime>10:00:00-05:00</cbc:IssueTime>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_fecha_generacion_v1(xml)
    
    assert resultado['valido'] is True

def test_validar_fecha_generacion_futura():
    """Prueba error cuando la fecha de generación es en el futuro."""
    manana = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%d')
    xml_content = f"""
    <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
        <cbc:IssueDate>{manana}</cbc:IssueDate>
        <cbc:IssueTime>10:00:00-05:00</cbc:IssueTime>
    </Invoice>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_fecha_generacion_v1(xml)
    
    assert resultado['valido'] is False
    assert resultado['id_error'] == IdTipoError.fecha_generacion_futura

def test_validar_fecha_validacion_exito():
    """Prueba validación exitosa de fecha de validación DIAN."""
    ayer = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    xml_content = f"""
    <AttachedDocument xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
                      xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2">
        <cac:ParentDocumentLineReference>
            <cac:DocumentReference>
                <cac:ResultOfVerification>
                    <cbc:ValidationDate>{ayer}</cbc:ValidationDate>
                    <cbc:ValidationTime>09:00:00-05:00</cbc:ValidationTime>
                    <cbc:ValidatorID>DIAN</cbc:ValidatorID>
                </cac:ResultOfVerification>
            </cac:DocumentReference>
        </cac:ParentDocumentLineReference>
    </AttachedDocument>
    """
    xml = etree.fromstring(xml_content)
    resultado = validar_fecha_validacion_dian_v1(xml)
    
    assert resultado['valido'] is True
    assert resultado['datos']['validador_id'] == 'DIAN'
