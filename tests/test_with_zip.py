import unittest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path
from dataclasses import dataclass

# Agregar el directorio raíz al path para importar los módulos
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from core.email_listener import EmailListener
from utils.factura_filter import FilterResult
from utils.malware_scanner import ScanResult

@dataclass
class MockValidation:
    es_valido: bool
    xml_path: MagicMock
    zip_path: MagicMock
    pdf_path: MagicMock
    errors: list
    archivos_encontrados: list = None
    motivo_error: str = None

class TestWithZipScenario(unittest.TestCase):
    
    @patch('core.email_listener.imaplib.IMAP4_SSL')
    @patch('core.email_listener.EmailRepository')
    @patch('core.email_listener.AttachmentHandler')
    @patch('core.email_listener.AttachmentValidator')
    @patch('core.email_listener.MalwareScanner')
    @patch('core.email_listener.AlertManager')
    @patch('core.email_listener.EmailParser')
    @patch('core.email_listener.get_publisher')
    def test_billing_email_with_zip_full_flow(self, 
                                            mock_pub, 
                                            mock_parser_cls,
                                            mock_alert_cls, 
                                            mock_scanner_cls, 
                                            mock_validator_cls, 
                                            mock_handler_cls, 
                                            mock_repo_cls, 
                                            mock_imap):
        """Prueba que un correo con ZIP siga todo el flujo de ingesta."""
        
        # 1. Configurar mocks
        mock_repo = mock_repo_cls.return_value
        mock_handler = mock_handler_cls.return_value
        mock_parser = mock_parser_cls.return_value
        mock_alert = mock_alert_cls.return_value
        mock_validator = mock_validator_cls.return_value
        mock_scanner = mock_scanner_cls.return_value
        
        listener = EmailListener()
        uid = b'50'
        asunto = "811028188;EMPRESA;FAC-123;01;EMPRESA"
        
        mock_conn = MagicMock()
        mock_conn.uid.return_value = ('OK', [(None, b'Subject: ' + asunto.encode() + b'\r\n\r\nBody')])
        
        parsed = {"nit": "811028188", "num_factura": "FAC-123", "asunto_original": asunto, "es_reenvio": False}
        mock_parser.parsear.return_value = parsed
        
        with patch('core.email_listener.FacturaFilter') as MockFilter:
            filter_instance = MockFilter.return_value
            filter_instance.es_facturacion.return_value = True
            filter_instance.evaluar.return_value = FilterResult(es_factura=True, motivo_rechazo=None, parsed_subject=parsed)
            
            # Mock de archivos usando MagicMock para simular Path y sus métodos
            mock_zip_path = MagicMock(spec=Path)
            mock_zip_path.name = "factura.zip"
            mock_handler._tiene_adjunto_zip.return_value = True
            mock_repo.guardar_correo_entrante.return_value = 1001
            mock_handler.descargar_zip.return_value = mock_zip_path
            
            mock_scanner.escanear_archivo.return_value = ScanResult(seguro=True, nivel_riesgo="BAJO", detalle="Limpio")
            
            mock_xml_path = MagicMock(spec=Path)
            mock_xml_path.name = "factura.xml"
            mock_pdf_path = MagicMock(spec=Path)
            mock_pdf_path.name = "factura.pdf"
            
            mock_validator.validar_zip.return_value = MockValidation(
                es_valido=True, xml_path=mock_xml_path, zip_path=mock_zip_path, pdf_path=mock_pdf_path, errors=[], archivos_encontrados=[]
            )
            
            mock_handler.construir_ruta_destino.return_value = MagicMock(spec=Path)
            
            # EJECUTAR
            resultado = listener._procesar_correo(mock_conn, uid)
            
            # ASERCIONES
            self.assertTrue(resultado)
            mock_repo.guardar_correo_entrante.assert_called_once()
            mock_handler.descargar_zip.assert_called_once()
            
            # Verificar que se llamó al método corregido
            mock_handler.construir_ruta_destino.assert_called()
            
            print("\nTest pasado: El flujo con ZIP se completo correctamente (mockeando operaciones de archivo).")

if __name__ == "__main__":
    unittest.main()
