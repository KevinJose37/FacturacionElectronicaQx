import pytest
from unittest.mock import MagicMock, patch
from core.email_listener import EmailListener
from utils.email_parser import ParsedSubject
from utils.factura_filter import FilterResult

@pytest.fixture
def mock_listener():
    with patch('core.email_listener.imaplib.IMAP4_SSL'), \
         patch('core.email_listener.EmailRepository'), \
         patch('core.email_listener.AttachmentHandler'), \
         patch('core.email_listener.AttachmentValidator'), \
         patch('core.email_listener.MalwareScanner'), \
         patch('core.email_listener.AlertManager'), \
         patch('core.email_listener.get_publisher'):
        
        listener = EmailListener()
        # Mock internal components
        listener._repository = MagicMock()
        listener._attachment_handler = MagicMock()
        listener._validator = MagicMock()
        listener._parser = MagicMock()
        listener._alert_manager = MagicMock()
        
        return listener

def test_billing_email_without_zip_is_registered(mock_listener):
    """Prueba que un correo de facturación sin ZIP se registre en la BD."""
    
    # Configurar mocks
    uid = b'123'
    asunto = "811028188;EMPRESA TEST;FAC-001;01;EMPRESA TEST"
    
    # 1. Mock de conexión IMAP
    mock_conn = MagicMock()
    mock_conn.uid.return_value = ('OK', [b' (RFC822 {100}\r\nDate: Mon, 1 Jan 2024 10:00:00 +0000\r\nSubject: ' + asunto.encode() + b'\r\n\r\nBody)'])
    
    # 2. Mock de parser
    parsed = {
        "nit": "811028188",
        "num_factura": "FAC-001",
        "asunto_original": asunto
    }
    mock_listener._parser.parsear.return_value = parsed
    
    # 3. Mock de AttachmentHandler (NO tiene ZIP)
    mock_listener._attachment_handler._tiene_adjunto_zip.return_value = False
    
    # 4. Mock de Filtro (Es facturación pero sin ZIP)
    # Simulamos que es_facturacion retorna True (ya que tiene NIT)
    with patch('core.email_listener.FacturaFilter') as MockFilter:
        instance = MockFilter.return_value
        instance.es_facturacion.return_value = True
        
        # Evaluar retorna fallo por falta de ZIP
        instance.evaluar.return_value = FilterResult(
            es_factura=False, 
            motivo_rechazo="SIN_ADJUNTO_ZIP"
        )
        
        # 5. Configurar retorno de repositorio para simular registro exitoso
        mock_listener._repository.guardar_correo_entrante.return_value = 1001 # ID generado
        
        # Ejecutar
        resultado = mock_listener._procesar_correo(mock_conn, uid)
        
        # ASERCIONES
        # A. Debe haberse llamado a guardar_correo_entrante
        mock_listener._repository.guardar_correo_entrante.assert_called_once()
        
        # B. No debe haberse llamado a descargar_zip (porque no tiene zip)
        mock_listener._attachment_handler.descargar_zip.assert_not_called()
        
        # C. Debe haberse llamado a adjunto_incompleto (alerta de falta de ZIP)
        mock_listener._alert_manager.adjunto_incompleto.assert_called_once_with(
            email_uid='unknown-1714444444', # O el ID generado por el mock
            archivos=[],
            motivo="El correo de facturación no contiene un archivo ZIP adjunto"
        )
        # Nota: el email_uid en el test dependerá de cómo se genere en _extraer_id_mensaje si no hay header
        
        # D. El resultado debe ser True (el correo fue "atendido" satisfactoriamente para el listener)
        assert resultado is True
        
        # E. Debe haberse marcado como leído (\Seen)
        mock_conn.uid.assert_any_call("store", uid, "+FLAGS", "\\Seen")

if __name__ == "__main__":
    pytest.main([__file__])
