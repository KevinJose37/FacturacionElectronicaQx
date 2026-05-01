-- Migration 001: Agregar columna tipo_documento a facturacion.factura
-- Tipos válidos: FE (Factura electrónica), NC (Nota crédito), ND (Nota débito), DS (Documento soporte)
-- Default 'FE' para registros existentes ya que el sistema solo procesa facturas electrónicas actualmente.

ALTER TABLE facturacion.factura
ADD COLUMN IF NOT EXISTS tipo_documento VARCHAR(4) NOT NULL DEFAULT 'FE';

COMMENT ON COLUMN facturacion.factura.tipo_documento IS 'Tipo de documento electrónico: FE=Factura, NC=Nota crédito, ND=Nota débito, DS=Documento soporte';
