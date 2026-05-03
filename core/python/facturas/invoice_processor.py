"""Orquestador principal del procesamiento de facturas electrónicas XML.

Flujo:
1. Consulta EVENTO_INGESTA pendientes (XML tipo 2).
2. Agrupa por familia (padre + hijos: AttachedDocument, Invoice, ApplicationResponse).
3. Para el Invoice: ejecuta validaciones req_01-18 y puebla las tablas.
4. Para el ApplicationResponse: ejecuta req_07.
5. Para el AttachedDocument: ejecuta req_06.
6. Cada validación genera un PROCESO_INGESTA.
7. Al completar, marca los EVENTO_INGESTA como PROCESADO.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from config import get_postgres_config
from core.python.facturas.invoice_repository import InvoiceRepository
from core.python.utils.xml_utils import parsear_xml_bytes
from metadata.db_metadata import IdEstadoProceso, IdTipoProceso, IdTipoError
from utils.s3_utils import obtener_xml_s3

# Validators
from core.python.validators.req_01_denominacion import validar_denominacion_v1
from core.python.validators.req_02_vendedor import validar_emisor_v1
from core.python.validators.req_03_adquiriente import validar_adquiriente_v1
from core.python.validators.req_04_numeracion import validar_numeracion_dian_v1
from core.python.validators.req_05_fecha_generacion import validar_fecha_generacion_v1
from core.python.validators.req_06_fecha_validacion import validar_fecha_validacion_dian_v1
from core.python.validators.req_07_factura_validacion_dian import validar_documento_validacion_dian_v1
from core.python.validators.req_08_items import validar_lineas_factura_v1
from core.python.validators.req_09_valor import validar_valor_total_v1
from core.python.validators.req_10_forma_pago import validar_forma_pago_v1
from core.python.validators.req_11_medio_pago import validar_medio_pago_v1
from core.python.validators.req_12_calidad_tributaria import validar_calidad_tributaria_v1
from core.python.validators.req_13_impuestos import validar_impuestos_v1
from core.python.validators.req_14_firma_digital import validar_firma_digital_v1
from core.python.validators.req_15_cufe import validar_cufe_v1
from core.python.validators.req_16_qr_code import validar_qr_code_v1
from core.python.validators.req_17_anexo_tecnico import validar_anexo_tecnico_v1
from core.python.validators.req_18_proveedor_software import validar_proveedor_software_v1

logger = logging.getLogger(__name__)

MAX_REINTENTOS = int(os.environ.get('MAX_REINTENTOS_FACTURA', '3'))
MAX_WORKERS = int(os.environ.get('MAX_WORKERS_FACTURA', '4'))


class InvoiceProcessor:
    """Procesador principal de facturas electrónicas."""

    def __init__(self, config: Optional[dict] = None):
        self._repo = InvoiceRepository(config or get_postgres_config())
        self._ruta_ca = os.environ.get('RUTA_CA_CONFIABLE_XML_DSIG')
        self._ruta_xsd = os.environ.get('RUTA_XSD_UBL_INVOICE')

    # ------------------------------------------------------------------
    # Punto de entrada
    # ------------------------------------------------------------------

    def procesar_pendientes(self, limite: int = 50) -> dict:
        """Procesa todos los eventos pendientes.

        Returns:
            dict con conteo de éxitos y fallos.
        """
        resultados = {'exitosos': 0, 'fallidos': 0, 'omitidos': 0}

        with self._repo.get_connection() as conn:
            eventos = self._repo.obtener_eventos_pendientes(conn, limite)
            conn.commit()

        if not eventos:
            logger.info('No hay eventos pendientes de procesamiento.')
            return resultados

        # Agrupar por adjunto_padre_id para procesar familias
        familias = self._agrupar_por_familia(eventos)
        logger.info('Procesando %d familias de XMLs.', len(familias))

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futuros = {
                executor.submit(self._procesar_familia, familia): familia_id
                for familia_id, familia in familias.items()
            }
            for futuro in as_completed(futuros):
                familia_id = futuros[futuro]
                try:
                    exito = futuro.result()
                    if exito:
                        resultados['exitosos'] += 1
                    else:
                        resultados['fallidos'] += 1
                except Exception as exc:
                    logger.exception('Error procesando familia %s: %s', familia_id, exc)
                    resultados['fallidos'] += 1

        logger.info(
            'Procesamiento completado: %d exitosos, %d fallidos, %d omitidos.',
            resultados['exitosos'], resultados['fallidos'], resultados['omitidos'],
        )
        return resultados

    def _agrupar_por_familia(self, eventos: list[dict]) -> dict:
        """Agrupa eventos por su adjunto_padre_id."""
        familias = {}
        for ev in eventos:
            padre_id = ev.get('adjunto_padre_id') or ev['adjunto_id']
            if padre_id not in familias:
                familias[padre_id] = []
            familias[padre_id].append(ev)
        return familias

    # ------------------------------------------------------------------
    # Procesamiento de una familia
    # ------------------------------------------------------------------

    def _procesar_familia(self, eventos: list[dict]) -> bool:
        """Procesa una familia de XMLs (AttachedDocument + Invoice + AR)."""
        # Clasificar por tipo de nombre
        invoice_ev = None
        ar_ev = None
        ad_ev = None

        for ev in eventos:
            nombre = (ev.get('nombre_archivo') or '').lower()
            if '_invoice' in nombre:
                invoice_ev = ev
            elif '_applicationresponse' in nombre:
                ar_ev = ev
            else:
                ad_ev = ev

        if not invoice_ev:
            logger.warning('Familia sin XML Invoice, omitiendo.')
            return False

        with self._repo.get_connection() as conn:
            try:
                exito = self._ejecutar_pipeline(conn, invoice_ev, ar_ev, ad_ev)
                if exito:
                    conn.commit()
                else:
                    conn.rollback()
                return exito
            except Exception as exc:
                conn.rollback()
                logger.exception('Error en pipeline: %s', exc)
                self._manejar_error_evento(conn, invoice_ev, str(exc))
                conn.commit()
                return False

    def _ejecutar_pipeline(
        self,
        conn,
        invoice_ev: dict,
        ar_ev: Optional[dict],
        ad_ev: Optional[dict],
    ) -> bool:
        """Ejecuta el pipeline de validaciones para una factura."""
        adjunto_id = invoice_ev['adjunto_id']
        s3_key = invoice_ev['uri_almacenamiento']
        sha256_actual = invoice_ev.get('sha256')

        # 1. Descargar y parsear Invoice XML desde S3
        xml_invoice = obtener_xml_s3(s3_key)
        if xml_invoice is None:
            self._repo.crear_proceso_ingesta(
                conn, adjunto_id, IdTipoProceso.validacion_cufe,
                f'Error al descargar/parsear XML desde S3: {s3_key}',
                IdEstadoProceso.error,
            )
            return False

        # 2. CUFE — PASO BLOQUEANTE
        res_cufe = validar_cufe_v1(xml_invoice)
        cufe = res_cufe['datos'].get('cufe')
        self._repo.crear_proceso_ingesta(
            conn, adjunto_id, IdTipoProceso.validacion_cufe,
            res_cufe['mensaje'],
            IdEstadoProceso.procesado if res_cufe['valido'] else IdEstadoProceso.error,
        )
        if not cufe:
            return False

        # 3. Idempotencia por CUFE
        factura_existente = self._repo.buscar_factura_por_cufe(conn, cufe)
        if factura_existente:
            sha256_existente = factura_existente.get('sha256')
            if sha256_existente == sha256_actual:
                logger.info('CUFE %s ya procesado con mismo SHA256, omitiendo.', cufe[:20])
                self._repo.marcar_evento_procesado(conn, adjunto_id)
                if ar_ev:
                    self._repo.marcar_evento_procesado(conn, ar_ev['adjunto_id'])
                if ad_ev:
                    self._repo.marcar_evento_procesado(conn, ad_ev['adjunto_id'])
                return True
            logger.info('CUFE %s existe con SHA256 diferente, reprocesando.', cufe[:20])

        # 4. Pipeline de validaciones del Invoice
        res_denom = validar_denominacion_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.validacion_denominacion, res_denom)

        res_emisor = validar_emisor_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.extraccion_emisor, res_emisor)

        res_adq = validar_adquiriente_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.extraccion_adquiriente, res_adq)

        res_num = validar_numeracion_dian_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.validacion_numeracion, res_num)

        res_fecha = validar_fecha_generacion_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.validacion_fecha_generacion, res_fecha)

        res_items = validar_lineas_factura_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.extraccion_lineas, res_items)

        res_valor = validar_valor_total_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.validacion_valor_total, res_valor)

        res_forma = validar_forma_pago_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.extraccion_forma_pago, res_forma)

        codigo_forma = res_forma['datos'].get('codigo_forma_pago')
        res_medio = validar_medio_pago_v1(xml_invoice, codigo_forma)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.extraccion_medio_pago, res_medio)

        res_fiscal = validar_calidad_tributaria_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.extraccion_calidad_tributaria, res_fiscal)

        res_imp = validar_impuestos_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.extraccion_impuestos, res_imp)

        res_firma = validar_firma_digital_v1(xml_invoice, self._ruta_ca)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.validacion_firma_digital, res_firma)

        res_qr = validar_qr_code_v1(xml_invoice, cufe)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.extraccion_qr, res_qr)

        res_anexo = validar_anexo_tecnico_v1(xml_invoice, self._ruta_xsd)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.validacion_anexo_tecnico, res_anexo)

        res_sw = validar_proveedor_software_v1(xml_invoice)
        self._registrar_proceso(conn, adjunto_id, IdTipoProceso.extraccion_software, res_sw)

        # 5. Validaciones del ApplicationResponse (req_07)
        xml_ar = None
        if ar_ev:
            xml_ar = obtener_xml_s3(ar_ev['uri_almacenamiento'])

        res_dian = validar_documento_validacion_dian_v1(xml_invoice, xml_ar)
        ar_adjunto = ar_ev['adjunto_id'] if ar_ev else adjunto_id
        self._registrar_proceso(conn, ar_adjunto, IdTipoProceso.validacion_documento_dian, res_dian)

        # 6. Validaciones del AttachedDocument (req_06)
        if ad_ev:
            xml_ad = obtener_xml_s3(ad_ev['uri_almacenamiento'])
            if xml_ad is not None:
                res_fv = validar_fecha_validacion_dian_v1(xml_ad)
            else:
                res_fv = {'valido': False, 'mensaje': 'No se pudo descargar AttachedDocument.', 'datos': {}}
            self._registrar_proceso(conn, ad_ev['adjunto_id'], IdTipoProceso.validacion_fecha_validacion, res_fv)

        # 7. Poblar tablas de BD
        self._poblar_tablas(
            conn, adjunto_id, cufe, res_denom, res_emisor, res_adq,
            res_num, res_fecha, res_valor, res_firma, res_qr,
            res_items, res_imp, res_forma, res_medio, res_fiscal, res_sw,
        )

        # 8. Marcar eventos como procesados
        self._repo.marcar_evento_procesado(conn, adjunto_id)
        if ar_ev:
            self._repo.marcar_evento_procesado(conn, ar_ev['adjunto_id'])
        if ad_ev:
            self._repo.marcar_evento_procesado(conn, ad_ev['adjunto_id'])

        logger.info('Factura procesada exitosamente: CUFE=%s', cufe[:20])
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _registrar_proceso(self, conn, adjunto_id: int, tipo: int, resultado: dict) -> None:
        """Registra un paso de validación en PROCESO_INGESTA."""
        estado = IdEstadoProceso.procesado if resultado['valido'] else IdEstadoProceso.error
        self._repo.crear_proceso_ingesta(conn, adjunto_id, tipo, resultado['mensaje'], estado)

    def _poblar_tablas(self, conn, adjunto_id, cufe, res_denom, res_emisor,
                       res_adq, res_num, res_fecha, res_valor, res_firma,
                       res_qr, res_items, res_imp, res_forma, res_medio,
                       res_fiscal, res_sw) -> None:
        """Puebla las tablas de facturación con los datos validados."""
        try:
            # TERCERO emisor
            datos_emisor = res_emisor['datos']
            id_emisor = self._repo.upsert_tercero(conn, {
                'numero_documento': datos_emisor.get('numero_documento') or 'DESCONOCIDO',
                'tipo_documento': datos_emisor.get('scheme_name') or '31',
                'digito_verificador': datos_emisor.get('digito_verificador'),
                'razon_social': datos_emisor.get('razon_social'),
                'nombre_comercial': datos_emisor.get('nombre_comercial'),
                'correo_contacto': datos_emisor.get('correo_contacto'),
                'telefono_contacto': datos_emisor.get('telefono_contacto'),
                'codigo_ciiu': datos_emisor.get('codigo_ciiu'),
            })

            # TERCERO adquiriente
            datos_adq = res_adq['datos']
            id_adq = self._repo.upsert_tercero(conn, {
                'numero_documento': datos_adq.get('numero_documento') or 'DESCONOCIDO',
                'tipo_documento': datos_adq.get('scheme_name') or '13',
                'digito_verificador': datos_adq.get('digito_verificador'),
                'razon_social': datos_adq.get('razon_social'),
                'nombre_comercial': datos_adq.get('nombre_comercial'),
                'correo_contacto': datos_adq.get('correo_contacto'),
                'telefono_contacto': datos_adq.get('telefono_contacto'),
                'codigo_ciiu': None,
            })

            # AUTORIZACION_NUMERACION_DIAN
            id_autorizacion = None
            datos_num = res_num['datos']
            if datos_num.get('numero_autorizacion'):
                id_autorizacion = self._repo.upsert_autorizacion(conn, {
                    'numero_autorizacion': datos_num['numero_autorizacion'],
                    'prefijo': datos_num.get('prefijo') or '',
                    'rango_desde': datos_num.get('rango_desde'),
                    'rango_hasta': datos_num.get('rango_hasta'),
                    'fecha_inicio': datos_num.get('fecha_inicio_vigencia'),
                    'fecha_fin': datos_num.get('fecha_fin_vigencia'),
                })

            # Fecha de generación
            d_fecha = res_fecha['datos']
            fecha_gen = None
            if d_fecha.get('fecha_generacion') and d_fecha.get('hora_generacion'):
                try:
                    fecha_str = f"{d_fecha['fecha_generacion']}T{d_fecha['hora_generacion']}"
                    fecha_gen = datetime.fromisoformat(fecha_str)
                except Exception:
                    fecha_gen = datetime.now(tz=timezone.utc)
            else:
                fecha_gen = datetime.now(tz=timezone.utc)

            # Valor total
            d_valor = res_valor['datos']
            valor_total = None
            if d_valor.get('valor_a_pagar'):
                try:
                    valor_total = Decimal(d_valor['valor_a_pagar'])
                except Exception:
                    pass

            # FACTURA
            d_qr = res_qr['datos']
            d_firma = res_firma['datos']
            d_denom = res_denom['datos']
            d_pago = res_forma['datos']

            id_factura = self._repo.insertar_factura(conn, {
                'cufe': cufe,
                'denominacion': d_denom.get('denominacion'),
                'prefijo': datos_num.get('prefijo') or '',
                'numero_factura': datos_num.get('numero_factura') or cufe[:20],
                'id_tercero_emisor': id_emisor,
                'id_tercero_adquiriente': id_adq,
                'id_autorizacion': id_autorizacion,
                'fecha_generacion': fecha_gen,
                'fecha_expedicion': None,
                'fecha_vencimiento': d_pago.get('fecha_vencimiento'),
                'moneda': d_valor.get('moneda') or 'COP',
                'valor_total': valor_total,
                'hash_firma': d_firma.get('hash_firma_digital'),
                'contenido_qr': d_qr.get('contenido_qr'),
                'adjunto_id': adjunto_id,
                'id_estado_proceso': IdEstadoProceso.procesado,
            })

            if id_factura <= 0:
                logger.error('No se pudo insertar la factura CUFE=%s', cufe[:20])
                return

            # DETALLE_FACTURA
            for linea in res_items['datos'].get('lineas', []):
                self._repo.insertar_detalle_factura(conn, id_factura, linea)

            # IMPUESTO_FACTURA
            for imp in res_imp['datos'].get('impuestos', []):
                self._repo.insertar_impuesto_factura(conn, id_factura, imp)

            # PAGO_FACTURA
            d_medio = res_medio['datos']
            self._repo.insertar_pago_factura(conn, id_factura, {
                'codigo_forma_pago': d_pago.get('codigo_forma_pago'),
                'codigo_medio_pago': d_medio.get('codigo_medio_pago'),
                'fecha_vencimiento': d_pago.get('fecha_vencimiento'),
                'duracion_plazo': d_pago.get('duracion_plazo'),
            })

            # CONDICION_FISCAL_FACTURA
            d_fiscal = res_fiscal['datos']
            if d_fiscal.get('responsabilidades_emisor'):
                self._repo.insertar_condicion_fiscal(
                    conn, id_factura, id_emisor, 'EMISOR',
                    d_fiscal['responsabilidades_emisor'],
                )
            if d_fiscal.get('responsabilidades_adquiriente'):
                self._repo.insertar_condicion_fiscal(
                    conn, id_factura, id_adq, 'ADQUIRIENTE',
                    d_fiscal['responsabilidades_adquiriente'],
                )

            # Registro final
            self._repo.crear_proceso_ingesta(
                conn, adjunto_id, IdTipoProceso.registro_factura,
                f'Factura registrada: ID={id_factura}, CUFE={cufe[:20]}...',
                IdEstadoProceso.procesado,
            )

        except Exception as exc:
            logger.exception('Error poblando tablas para CUFE=%s: %s', cufe[:20], exc)
            self._repo.crear_proceso_ingesta(
                conn, adjunto_id, IdTipoProceso.registro_factura,
                f'Error al registrar factura: {exc}',
                IdEstadoProceso.error,
            )

    def _manejar_error_evento(self, conn, evento: dict, error: str) -> None:
        """Maneja errores incrementando intentos o marcando como fallido."""
        try:
            intentos = self._repo.incrementar_intentos_evento(conn, evento['id_evento'])
            if intentos >= MAX_REINTENTOS:
                self._repo.actualizar_estado_evento(
                    conn, evento['id_evento'], IdEstadoProceso.fallido
                )
                self._repo.crear_proceso_ingesta(
                    conn, evento['adjunto_id'], IdTipoProceso.registro_factura,
                    f'Máximo de reintentos ({MAX_REINTENTOS}) excedido: {error}',
                    IdEstadoProceso.fallido,
                )
            else:
                self._repo.actualizar_estado_evento(
                    conn, evento['id_evento'], IdEstadoProceso.pendiente
                )
        except Exception:
            logger.exception('Error manejando fallo del evento %s', evento.get('id_evento'))


def run():
    """Punto de entrada para ejecución directa."""
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        stream=sys.stdout,
    )
    processor = InvoiceProcessor()
    resultados = processor.procesar_pendientes()
    logger.info('Resultados: %s', resultados)


if __name__ == '__main__':
    run()
