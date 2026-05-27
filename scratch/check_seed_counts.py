import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': int(os.environ.get('POSTGRES_PORT', '5433')),
    'dbname': os.environ.get('POSTGRES_DB', 'facturacion'),
    'user': os.environ.get('POSTGRES_USER', 'admin'),
    'password': os.environ.get('POSTGRES_PASSWORD', ''),
}

def check_counts():
    conn = psycopg.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    tables = [
        'tercero', 'archivo', 'correo_entrante', 'adjuntos_correo',
        'factura', 'detalle_factura', 'pago_factura', 'proceso_ingesta',
        'log_proceso', 'validacion_dian', 'evento_ingesta', 'factura_control'
    ]
    
    print("--- CONTEO DE REGISTROS EN LA BASE DE DATOS ---")
    for t in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM facturacion.{t}')
            count = cur.fetchone()[0]
            print(f'Tabla facturacion.{t:25} : {count} registros')
        except Exception as e:
            print(f'Tabla facturacion.{t:25} : ERROR ({e})')
            
    conn.close()

if __name__ == '__main__':
    check_counts()
