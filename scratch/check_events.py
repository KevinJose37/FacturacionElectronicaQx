import os
import psycopg
import json
from dotenv import load_dotenv
import yaml
from pathlib import Path

# Cargar config para obtener parámetros de conexión
load_dotenv()
config_path = Path("config/settings.yaml")
with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

pg_cfg = config["queue"]["postgres"]
password = os.getenv("POSTGRES_PASSWORD", "")

def check_db():
    try:
        conn = psycopg.connect(
            host=pg_cfg.get("host", "localhost"),
            port=pg_cfg.get("port", 5432),
            dbname=pg_cfg.get("dbname", "postgres"),
            user=pg_cfg.get("user", "postgres"),
            password=password
        )
        with conn.cursor() as cur:
            # 1. Verificar si la tabla existe
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'facturacion' 
                    AND table_name = 'evento_ingesta'
                );
            """)
            exists = cur.fetchone()[0]
            if not exists:
                print("❌ La tabla FACTURACION.EVENTO_INGESTA no existe.")
                return

            # 2. Contar registros
            cur.execute("SELECT COUNT(*) FROM FACTURACION.EVENTO_INGESTA;")
            count = cur.fetchone()[0]
            print(f"✅ Tabla encontrada. Registros actuales: {count}")

            if count > 0:
                print("\n--- Últimos 5 eventos ---")
                cur.execute("""
                    SELECT id_evento, fecha_creacion, estado, datos_json 
                    FROM FACTURACION.EVENTO_INGESTA 
                    ORDER BY fecha_creacion DESC LIMIT 5;
                """)
                for row in cur.fetchall():
                    print(f"ID: {row[0]} | Fecha: {row[1]} | Estado: {row[2]}")
                    # print(f"Datos: {json.dumps(row[3], indent=2)}") 

    except Exception as e:
        print(f"❌ Error al conectar a la DB: {e}")

if __name__ == "__main__":
    check_db()
