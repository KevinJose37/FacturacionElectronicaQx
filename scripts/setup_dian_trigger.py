import psycopg2

def create_trigger():
    sql = """
    CREATE OR REPLACE FUNCTION facturacion.fn_sincronizar_evento_dian_control()
    RETURNS TRIGGER AS $$
    BEGIN
        -- Solo actuar si el evento es uno de los requeridos (030, 032, 033)
        IF NEW.codigo_evento IN ('030', '032', '033') THEN
            -- Actualizar el campo eventos_dian_notif concatenando los nombres de eventos permitidos
            UPDATE facturacion.factura_control
            SET 
                eventos_dian_notif = (
                    SELECT string_agg(te.nombre_evento, ', ' ORDER BY edf.fecha_evento)
                    FROM facturacion.evento_dian_factura edf
                    JOIN facturacion.tipo_evento_dian te ON edf.codigo_evento = te.codigo_evento
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
