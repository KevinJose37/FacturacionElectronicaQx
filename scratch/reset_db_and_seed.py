import os
import sys
import psycopg
from dotenv import load_dotenv

# Asegurar que estamos en el directorio correcto y agregar al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar variables de entorno del archivo .env
load_dotenv()

# Obtener configuración de conexión de la base de datos
DB_CONFIG = {
    'host': os.environ.get('POSTGRES_HOST', 'localhost'),
    'port': int(os.environ.get('POSTGRES_PORT', '5433')),
    'dbname': os.environ.get('POSTGRES_DB', 'facturacion'),
    'user': os.environ.get('POSTGRES_USER', 'admin'),
    'password': os.environ.get('POSTGRES_PASSWORD', ''),
}

EXTRA_TABLES_SQL = """
ALTER TABLE FACTURACION.TERCERO ADD COLUMN IF NOT EXISTS RAZON_SOCIAL VARCHAR(300) NULL;
ALTER TABLE FACTURACION.TERCERO ADD COLUMN IF NOT EXISTS NOMBRE_COMERCIAL VARCHAR(300) NULL;

CREATE TABLE IF NOT EXISTS FACTURACION.ARCHIVO (
    ID_ARCHIVO          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    URI_ALMACENAJE      VARCHAR(255) NOT NULL,
    NOMBRE_ORIGINAL     VARCHAR(255) NOT NULL,
    TIPO_MIME           VARCHAR(100) NOT NULL,
    HASH_SHA256         VARCHAR(64) NOT NULL UNIQUE,
    TAMANO_BYTES        BIGINT NOT NULL,
    FECHA_CREACION      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS FACTURACION.VALIDACION_DIAN (
    ID_VALIDACION       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ID_FACTURA          BIGINT NOT NULL REFERENCES FACTURACION.FACTURA(ID_FACTURA) ON DELETE CASCADE,
    FECHA_VALIDACION    TIMESTAMPTZ NOT NULL,
    CODIGO_RESPUESTA    VARCHAR(50) NOT NULL,
    DESCRIPCION_RESPUESTA VARCHAR(300) NOT NULL,
    ID_ESTADO_PROCESO   INT NOT NULL REFERENCES FACTURACION.TIPO_ESTADO_PROCESO(ID_ESTADO_PROCESO)
);

CREATE TABLE IF NOT EXISTS FACTURACION.IMPUESTO_DETALLE_FACTURA (
    ID_DETALLE          BIGINT NOT NULL REFERENCES FACTURACION.DETALLE_FACTURA(ID_DETALLE) ON DELETE CASCADE,
    ID_IMPUESTO         VARCHAR(10) NOT NULL, -- Sin FK estricta para soportar el seed entero 1
    TARIFA              NUMERIC(9,4) NOT NULL CHECK (TARIFA >= 0),
    BASE_GRAVABLE       NUMERIC(18,2) NOT NULL CHECK (BASE_GRAVABLE >= 0),
    VALOR_IMPUESTO      NUMERIC(18,2) NOT NULL CHECK (VALOR_IMPUESTO >= 0),
    PRIMARY KEY (ID_DETALLE, ID_IMPUESTO, TARIFA)
);

CREATE TABLE IF NOT EXISTS FACTURACION.LOG_PROCESO (
    ID_PROCESO          BIGINT NOT NULL REFERENCES FACTURACION.PROCESO_INGESTA(ID_PROCESO_INGESTA) ON DELETE CASCADE,
    NUMERO_SECUENCIA    INT NOT NULL,
    CODIGO_ETAPA        VARCHAR(50) NOT NULL,
    ID_ESTADO_PROCESO   INT NOT NULL REFERENCES FACTURACION.TIPO_ESTADO_PROCESO(ID_ESTADO_PROCESO),
    FECHA_INICIO        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FECHA_FIN           TIMESTAMPTZ NULL,
    DETALLE_JSON        JSONB NULL,
    DETALLE_ERROR       TEXT NULL,
    PRIMARY KEY (ID_PROCESO, NUMERO_SECUENCIA)
);

CREATE TABLE IF NOT EXISTS FACTURACION.ESCANEO_SEGURIDAD (
    ID_ESCANEO          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ADJUNTO_ID          BIGINT NOT NULL REFERENCES FACTURACION.ADJUNTOS_CORREO(ADJUNTO_ID) ON DELETE CASCADE,
    RESULTADO           VARCHAR(50) NOT NULL,
    DETALLE             TEXT NULL,
    FECHA_ESCANEO       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION facturacion.fn_sincronizar_evento_dian_control()
RETURNS TRIGGER AS $$
BEGIN
    -- Verificar si la factura es de CONTADO (código '1')
    -- Si es contado, no se sincronizan los eventos en la tabla de control (se mantienen vacíos)
    IF EXISTS (
        SELECT 1 FROM facturacion.pago_factura 
        WHERE id_factura = NEW.id_factura 
          AND codigo_forma_pago = '1'
    ) THEN
        RETURN NEW;
    END IF;

    -- Solo actuar si el evento es uno de los requeridos (030, 032, 033)
    IF NEW.codigo_evento IN ('030', '032', '033') THEN
        -- Actualizar el campo eventos_dian_notif concatenando los códigos de eventos permitidos
        UPDATE facturacion.factura_control
        SET 
            eventos_dian_notif = (
                SELECT string_agg(edf.codigo_evento, ', ' ORDER BY edf.fecha_evento)
                FROM facturacion.evento_dian_factura edf
                WHERE edf.id_factura = NEW.id_factura
                  AND edf.codigo_evento IN ('030', '032', '033')
            ),
            -- También sincronizar los checkboxes automáticamente
            acuso_recibido = CASE 
                WHEN NEW.codigo_evento = '030' THEN TRUE 
                ELSE acuso_recibido 
            END,
            recibido_bien_servicio = CASE 
                WHEN NEW.codigo_evento = '032' THEN TRUE 
                ELSE recibido_bien_servicio 
            END,
            aceptacion_expresa = CASE 
                WHEN NEW.codigo_evento = '033' THEN TRUE 
                ELSE aceptacion_expresa 
            END,
            fecha_actualizacion = NOW()
        WHERE id_factura = NEW.id_factura;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sincronizar_evento_dian_control ON facturacion.evento_dian_factura;

CREATE TRIGGER trg_sincronizar_evento_dian_control
AFTER INSERT OR UPDATE ON facturacion.evento_dian_factura
FOR EACH ROW
EXECUTE FUNCTION facturacion.fn_sincronizar_evento_dian_control();
"""

print(f"Conectando a la base de datos {DB_CONFIG['dbname']} en {DB_CONFIG['host']}:{DB_CONFIG['port']}...")

def reset_and_seed():
    # 1. Conectar a PostgreSQL
    conn = psycopg.connect(**DB_CONFIG)
    conn.autocommit = False
    
    try:
        cur = conn.cursor()
        
        # 1.5. Terminar otras conexiones activas y limpiar la base de datos con reintentos para evitar deadlocks
        conn.autocommit = True
        for intento in range(15):
            try:
                print(f"Intento {intento+1} de limpieza: Terminando otras conexiones y ejecutando DROP SCHEMA...")
                cur.execute("""
                    SELECT pg_terminate_backend(pid) 
                    FROM pg_stat_activity 
                    WHERE datname = 'facturacion' 
                      AND pid <> pg_backend_pid();
                """)
                cur.execute("DROP SCHEMA IF EXISTS FACTURACION CASCADE;")
                print("Base de datos limpiada correctamente.")
                break
            except Exception as e:
                print(f"Intento {intento+1} falló debido a deadlock/error: {e}. Reintentando en 0.5s...")
                import time
                time.sleep(0.5)
        else:
            raise Exception("No se pudo limpiar la base de datos tras 15 intentos debido a deadlocks concurrentes.")
        conn.autocommit = False
        
        # 3. Ejecutar modelo_facturacion.sql para crear tablas y catálogos
        print("Ejecutando modelo_facturacion.sql...")
        with open("modelo_facturacion.sql", "r", encoding="utf-8") as f:
            sql_schema = f.read()
        cur.execute(sql_schema)
        print("Esquema y catálogos de modelo_facturacion.sql creados en la transacción.")
        
        # 4. Crear las tablas y columnas adicionales requeridas por el seed/logs
        print("Creando tablas y columnas adicionales (TERCERO razon_social/nombre_comercial, ARCHIVO, VALIDACION_DIAN, LOG_PROCESO, etc.)...")
        cur.execute(EXTRA_TABLES_SQL)
        print("Tablas y columnas adicionales creadas en la transacción.")
        
        # 5. Ejecutar migración migrations/add_verificacion_grafica_detalle.sql
        print("Ejecutando migración add_verificacion_grafica_detalle.sql...")
        with open("migrations/add_verificacion_grafica_detalle.sql", "r", encoding="utf-8") as f:
            sql_migration = f.read()
        cur.execute(sql_migration)
        print("Migración de campos adicionales completada en la transacción.")
        
        # 6. Configurar el trigger de eventos DIAN usando psycopg
        print("Configurando el trigger en la base de datos...")
        cur.execute(TRIGGER_SQL)
        print("Trigger y función creados en la transacción.")
        
        # Consolidar toda la DDL en un solo commit para evitar deadlocks de procesos concurrentes
        conn.commit()
        print("Esquema, tablas extras, migración y trigger commiteados exitosamente.")
        
        cur.close()
        conn.close()
        
        # 7. Ejecutar seed para poblar con datos de prueba realistas
        print("Ejecutando seed de datos por defecto...")
        from scripts.seed import ejecutar_seed
        ejecutar_seed()
        
        print("\n¡Operación completada exitosamente!")
        
    except Exception as e:
        print(f"\nERROR durante la ejecución: {e}")
        try:
            conn.rollback()
            conn.close()
        except:
            pass
        sys.exit(1)

if __name__ == '__main__':
    reset_and_seed()
