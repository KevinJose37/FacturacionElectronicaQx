import psycopg2

def create_trigger():
    sql = """
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
                aceptacion_empresa = CASE 
                    WHEN NEW.codigo_evento = '033' THEN TRUE 
                    ELSE aceptacion_empresa 
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
    
    try:
        conn = psycopg2.connect(
            host='217.216.85.110', 
            port=5433, 
            dbname='facturacion', 
            user='admin', 
            password='mysecretpassword'
        )
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()
        print("Trigger y función creados exitosamente en la base de datos.")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_trigger()
