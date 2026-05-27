-- Migración: Alterar OBSERVACION en PROCESO_INGESTA a TEXT
-- Evita errores de StringDataRightTruncation al almacenar observaciones largas de fallos de validación o rechazos múltiples.

ALTER TABLE FACTURACION.PROCESO_INGESTA 
    ALTER COLUMN OBSERVACION TYPE TEXT;

COMMENT ON COLUMN FACTURACION.PROCESO_INGESTA.OBSERVACION IS
    'Detalle u observación del proceso, sin límite de longitud para permitir registrar múltiples motivos de rechazo.';
