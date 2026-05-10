"""Prueba simulada del worker para Verificación Gráfica Híbrida."""

import asyncio
import logging
from pathlib import Path
import fitz  # PyMuPDF

# Importamos el nuevo controlador
from core.python.verificacion_grafica.controlador import verificar_representacion_grafica

import sys
import os

# Agregar el directorio raíz al path para importar los módulos correctamente
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

# Configurar logging básico para ver la salida
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger(__name__)

# Aseguramos que la carpeta exista
Path("tests/validaciones").mkdir(exist_ok=True, parents=True)

def crear_pdf_de_prueba(ruta: str):
    """Crea un PDF válido con la información requerida."""
    logger.info(f"Creando PDF de prueba en: {ruta}")
    doc = fitz.open()
    pagina = doc.new_page()
    
    # Escribimos los datos en el PDF (Simulando una factura generada por software)
    textos = [
        "Factura Electrónica de Venta",
        "Empresa Ficticia S.A.S",
        "NIT: 900123456",
        "Cliente Corporativo LTDA",
        "Factura No: SETP990067604",
        "Total a pagar: $ 1.500.250,00",
        "CUFE: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6"
    ]
    
    y = 50
    for texto in textos:
        pagina.insert_text((50, y), texto, fontsize=12)
        y += 20
        
    doc.save(ruta)
    doc.close()


async def main():
    logger.info("Iniciando prueba del Worker de Verificación Gráfica...")
    
    ruta_pdf = "tests/validaciones/factura_prueba.pdf"
    crear_pdf_de_prueba(ruta_pdf)
    
    # Estos son los datos extraídos del XML previamente por los validadores
    datos_factura = {
        "denominacion": "Factura Electrónica de Venta",
        "nit_emisor": "9001234567",
        "razon_social_emisor": "Empresa Ficticia S.A.S",
        "nit_adquiriente": "Cliente Corporativo LTDA",  # Para la heurística
        "numero_factura": "SETP990067604",
        "valor_total": "1500251.00",
        "cufe": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y56"
    }
    
    logger.info("Llamando al controlador de verificación gráfica...")
    # Llamamos a nuestra nueva implementación
    resultado = await verificar_representacion_grafica(ruta_pdf, datos_factura)
    
    logger.info("=== RESULTADO DE LA VERIFICACIÓN ===")
    logger.info(f"Aprobado: {resultado['aprobado']}")
    logger.info(f"Método utilizado: {resultado['metodo']}")
    
    if resultado['aprobado']:
        logger.info("¡PRUEBA EXITOSA! La verificación gráfica (PyMuPDF o IA) encontró todos los datos.")
    else:
        logger.warning("Fallo en la prueba:")
        for campo, info in resultado.get("campos", {}).items():
            # Soporta tanto el formato del validador local ('encontrado') como el de la IA ('presente')
            fue_encontrado = info.get("encontrado", False) or info.get("presente", False)
            if not fue_encontrado:
                valor_visto = info.get("valor_visto", "No detectado en la imagen")
                logger.warning(f"  - {campo}: Discrepancia. La IA/Local detectó: '{valor_visto}'")
        
        explicacion = resultado.get("explicacion")
        if explicacion:
            logger.info(f"  - Explicación de Innti: {explicacion}")

if __name__ == "__main__":
    asyncio.run(main())
