import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path para importar los módulos
root_dir = Path(r"c:\Users\ASUS\Documents\mariana\proyectos_dev_velvet\hackatones\FacturacionElectronicaQx")
sys.path.append(str(root_dir))

from utils.email_parser import EmailParser
from utils.factura_filter import FacturaFilter

def test_identification():
    parser = EmailParser()
    # Mock config
    config = {
        "filter": {
            "require_nit": True,
            "require_num_factura": True
        }
    }
    filtro = FacturaFilter(config)

    test_cases = [
        ("811028188;EMPRESA ABC;FAC-001;01;EMPRESA ABC", True, "Formato estándar con NIT"),
        ("Factura de venta FE-123", True, "Palabra clave 'Factura'"),
        ("Envío de Facturación electrónica", True, "Palabra clave 'Facturación'"),
        ("FE;900123456;Algo", True, "Palabra clave 'FE'"),
        ("Feliz día del padre", False, "Falso positivo 'Fe' dentro de palabra"),
        ("Importante: Favor revisar", False, "No es facturación"),
        ("Electronic bill for service", True, "Palabra clave en inglés"),
        ("Fwd: 811028188;EMPRESA ABC;FAC-001;01;EMPRESA ABC", True, "Reenvío con formato estándar"),
    ]

    print(f"{'Asunto':<60} | {'Esperado':<8} | {'Resultado':<8} | {'Status'}")
    print("-" * 100)
    
    for asunto, esperado, descripcion in test_cases:
        parsed = parser.parsear(asunto)
        resultado = filtro.es_facturacion(parsed)
        status = "PASS" if resultado == esperado else "FAIL"
        print(f"{asunto[:58]:<60} | {str(esperado):<8} | {str(resultado):<8} | {status} ({descripcion})")

if __name__ == "__main__":
    test_identification()
