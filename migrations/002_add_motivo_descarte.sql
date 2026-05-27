-- Migración: Añadir MOTIVO_DESCARTE a CORREO_ENTRANTE
-- Permite registrar correos no-factura para excluirlos de reprocesamiento
-- sin marcarlos como leídos en IMAP.

ALTER TABLE FACTURACION.CORREO_ENTRANTE 
    ADD COLUMN IF NOT EXISTS MOTIVO_DESCARTE VARCHAR(100) NULL;

COMMENT ON COLUMN FACTURACION.CORREO_ENTRANTE.MOTIVO_DESCARTE IS
    'Motivo por el cual el correo fue descartado (no-factura, rechazado, etc.). NULL si es válido para procesamiento.';

-- Índice parcial para consultas de exclusión por MESSAGE_ID
CREATE INDEX IF NOT EXISTS IX_CORREO_DESCARTADO 
    ON FACTURACION.CORREO_ENTRANTE (MESSAGE_ID) 
    WHERE MOTIVO_DESCARTE IS NOT NULL;
