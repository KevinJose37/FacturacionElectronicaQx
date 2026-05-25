-- Migration: Add MOTIVO_RECHAZO and VERIFICACION_GRAFICA_DETALLE columns to factura table
-- Run this migration on existing databases to add the new columns.
-- For fresh deployments, the columns are already in modelo_facturacion.sql.

-- MOTIVO_RECHAZO: Stores human-readable rejection reasons from manual PDF review
ALTER TABLE facturacion.factura 
ADD COLUMN IF NOT EXISTS motivo_rechazo TEXT DEFAULT NULL;

-- VERIFICACION_GRAFICA_DETALLE: Stores structured AI verification results as JSON
-- including campo-by-campo analysis with confidence scores
ALTER TABLE facturacion.factura 
ADD COLUMN IF NOT EXISTS verificacion_grafica_detalle JSONB DEFAULT NULL;

COMMENT ON COLUMN facturacion.factura.motivo_rechazo IS 
    'Texto con motivos de rechazo de la revisión manual de representación gráfica (Art. 11 Res. 000165)';

COMMENT ON COLUMN facturacion.factura.verificacion_grafica_detalle IS 
    'JSON con resultado detallado de la verificación gráfica IA: campos, confianza, método usado';
