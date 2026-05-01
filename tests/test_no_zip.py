import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Agregar el directorio raíz al path para importar los módulos
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from core.email_listener import EmailListener
from utils.factura_filter import FilterResult

class TestNoZipScenario(unittest.TestCase):
    
    @patch('core.email_listener.imaplib.IMAP4_SSL')
    @patch('core.email_listener.EmailRepository')
    @patch('core.email_listener.AttachmentHandler')
    @patch('core.email_listener.AttachmentValidator')
    @patch('core.email_listener.MalwareScanner')
    @patch('core.email_listener.AlertManager')
    @patch('core.email_listener.EmailParser')
    @patch('core.email_listener.get_publisher')
    def test_billing_email_without_zip_is_registered(self, 
                                                   mock_pub, 
                                                   mock_parser_cls,
                                                   mock_alert_cls, 
                                                   mock_scanner_cls, 
                                                   mock_validator_cls, 
                                                   mock_handler_cls, 
                                                   mock_repo_cls, 
                                                   mock_imap):
        """Prueba que un correo de facturación sin ZIP se registre en la BD."""
        
        # 1. Configurar mocks de las clases
        mock_repo = mock_repo_cls.return_value
        mock_handler = mock_handler_cls.return_value
        mock_parser = mock_parser_cls.return_value
        mock_alert = mock_alert_cls.return_value
        
        # 2. Instanciar Listener
        listener = EmailListener()
        
        # 3. Configurar datos de prueba
        uid = b'123'
        asunto = "811028188;EMPRESA TEST;FAC-001;01;EMPRESA TEST"
        
        # 4. Mock de conexión IMAP
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ('OK', [(None, b' (RFC822 {100}\r\nDate: Mon, 1 Jan 2024 10:00:00 +0000\r\nSubject: ' + asunto.encode() + b'\r\n\r\nBody)')])
        
        # 5. Mock de resultados
        parsed = {
            "nit": "811028188",
            "num_factura": "FAC-001",
            "asunto_original": asunto,
            "es_reenvio": False
        }
        mock_parser.parsear.return_value = parsed
        mock_handler._tiene_adjunto_zip.return_value = False
        mock_repo.guardar_correo_entrante.return_value = 1001
        
        # 6. Mock de Filtro
        with patch('core.email_listener.FacturaFilter') as MockFilter:
            instance = MockFilter.return_value
            instance.es_facturacion.return_value = True
            instance.evaluar.return_value = FilterResult(
                es_factura=False, 
                motivo_rechazo="SIN_ADJUNTO_ZIP",
                parsed_subject=parsed
            )
            
            # EJECUTAR
            resultado = listener._procesar_correo(mock_conn, uid)
            
            # ASERCIONES
            # A. Debe haberse llamado a guardar_correo_entrante
            mock_repo.guardar_correo_entrante.assert_called_once()
            
            # B. Debe haberse llamado a adjunto_incompleto
            mock_alert.adjunto_incompleto.assert_called_once()
            
            # C. El resultado debe ser True
            self.assertTrue(resultado)
            
            print("\nTest pasado: El correo sin ZIP se registro y genero alerta correctamente.")

if __name__ == "__main__":
    unittest.main()
