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
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from config import get_postgres_config, load_yaml_config
from core.python.verificacion_grafica.service import extraer_cufe_pdf
from core.python.verificacion_grafica.controlador import verificar_representacion_grafica
from utils.alerts import AlertManager
from core.python.facturas.invoice_repository import InvoiceRepository
from metadata.db_metadata import (
    IdEstadoProceso,
    IdTipoArchivo,
    IdTipoProceso,
)
from metadata.path_s3 import RutasS3
from utils.s3_utils import copiar_archivo_s3, obtener_xml_s3, descargar_archivo_s3

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

_settings = load_yaml_config('settings.yaml')
_processor_cfg = _settings.get('invoice_processor', {})


class InvoiceProcessor:
    """Procesador principal de facturas electrónicas."""

    def __init__(self, config: Optional[dict] = None):
        self._repo = InvoiceRepository(config or get_postgres_config())
        self._ruta_ca = os.environ.get('RUTA_CA_CONFIABLE_XML_DSIG')
        self._ruta_xsd = os.environ.get('RUTA_XSD_UBL_INVOICE')
        self._alert_manager = AlertManager(_settings)
        self._max_reintentos = int(_processor_cfg.get('max_reintentos', 3))
        self._max_workers = int(_processor_cfg.get('max_workers', 4))

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

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futuros = {
                executor.submit(self._procesar_familia, familia): familia_id
                for familia_id, familia in familias.items()
            }
            for futuro in as_completed(futuros):
                familia_id = futuros[futuro]
                try:
                    estado = futuro.result()
                    if estado == 'ok':
                        resultados['exitosos'] += 1
                    elif estado == 'skip':
                        resultados['omitidos'] += 1
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

    def _agrupar_por_familia(self, eventos: list) -> dict:
        """Agrupa eventos por su raíz en el árbol de adjuntos.

        Usa ADJUNTO_RAIZ_ID (calculado vía CTE recursivo en la query) para que
        toda la cadena ZIP → AttachedDocument → (Invoice + ApplicationResponse)
        quede en una sola familia. Si la raíz no viene resuelta, recurre al
        padre directo o al propio adjunto como último fallback.
        """
        familias = {}
        for ev in eventos:
            raiz_id = (
                ev.get('adjunto_raiz_id')
                or ev.get('adjunto_padre_id')
                or ev['adjunto_id']
            )
            if raiz_id not in familias:
                familias[raiz_id] = []
            familias[raiz_id].append(ev)
        return familias

    # ------------------------------------------------------------------
    # Procesamiento de una familia
    # ------------------------------------------------------------------

    def _procesar_familia(self, eventos: list) -> str:
        """Procesa una familia de XMLs (AttachedDocument + Invoice + AR).

        Returns:
            'ok'   si la factura fue procesada exitosamente.
            'skip' si la familia no contiene Invoice procesable (huérfanos).
            'fail' si ocurrió un error durante el pipeline.
        """
        # Clasificar por tipo de nombre
        invoice_ev = None
        ar_ev = None
        ad_ev = None
        pdf_ev = None

        for ev in eventos:
            nombre = (ev.get('nombre_archivo') or '').lower()
            tipo = ev.get('id_tipo_archivo')
            if tipo == IdTipoArchivo.pdf:
                pdf_ev = ev
            elif '_invoice' in nombre:
                invoice_ev = ev
            elif '_applicationresponse' in nombre:
                ar_ev = ev
            else:
                ad_ev = ev

        # Promoción: si no hay _invoice explícito pero hay un XML genérico
        # (AttachedDocument original o XML sin sufijo), promoverlo a invoice_ev.
        # El pipeline extrae el Invoice embebido del AttachedDocument.
        if not invoice_ev and ad_ev:
            invoice_ev = ad_ev
            ad_ev = None

        # Si no hay PDF en los eventos pendientes, buscarlo en la familia completa en la BD
        if not pdf_ev and invoice_ev:
            with self._repo.get_connection() as conn:
                adjuntos_familia = self._repo.obtener_adjuntos_familia(conn, invoice_ev['adjunto_id'])
                for adj in adjuntos_familia:
                    if adj.get('id_tipo_archivo') == IdTipoArchivo.pdf:
                        pdf_ev = adj
                        break

        if not invoice_ev and pdf_ev and len(eventos) == 1:
            # Es un PDF huérfano
            return self._procesar_pdf_huerfano(pdf_ev)

        if not invoice_ev:
            nombres = [ev.get('nombre_archivo') for ev in eventos]
            logger.warning(
                'Familia sin XML Invoice, omitiendo huérfanos: %s', nombres
            )
            # Marcar los huérfanos como procesados para sacarlos de la cola
            with self._repo.get_connection() as conn:
                try:
                    for ev in eventos:
                        self._repo.marcar_evento_procesado(conn, ev['adjunto_id'])
                    conn.commit()
                except Exception:
                    conn.rollback()
                    logger.exception('Error marcando huérfanos como procesados')
            return 'skip'

        with self._repo.get_connection() as conn:
            try:
                exito = self._ejecutar_pipeline(conn, invoice_ev, ar_ev, ad_ev, pdf_ev)
                if exito:
                    conn.commit()
                    return 'ok'
                conn.rollback()
                return 'fail'
            except Exception as exc:
                conn.rollback()
                logger.exception('Error en pipeline: %s', exc)
                self._manejar_error_evento(conn, invoice_ev, str(exc))
                conn.commit()
                return 'fail'

    def _ejecutar_pipeline(
        self,
        conn,
        invoice_ev: dict,
        ar_ev: Optional[dict],
        ad_ev: Optional[dict],
        pdf_ev: Optional[dict] = None,
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

        # 1b. Si es AttachedDocument, extraer el Invoice embebido del CDATA
        from lxml import etree
        tag_local = etree.QName(xml_invoice).localname
        xml_ar_from_ad = None  # ApplicationResponse embebido en el AD
        if tag_local == 'AttachedDocument':
            ns = {
                'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
                'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            }
            # Extraer ApplicationResponse del ParentDocumentLineReference
            xpath_ar = (
                './/cac:ParentDocumentLineReference'
                '//cac:Attachment/cac:ExternalReference/cbc:Description'
            )
            nodos_ar = xml_invoice.xpath(xpath_ar, namespaces=ns)
            if nodos_ar and nodos_ar[0].text:
                try:
                    xml_ar_from_ad = etree.fromstring(nodos_ar[0].text.strip().encode('utf-8'))
                    ar_local = etree.QName(xml_ar_from_ad).localname
                    if ar_local == 'ApplicationResponse':
                        logger.info(
                            'ApplicationResponse extraído del AttachedDocument (adjunto=%s).',
                            adjunto_id,
                        )
                    else:
                        logger.warning(
                            'Nodo ParentDocumentLineReference no contiene ApplicationResponse (tipo=%s).',
                            ar_local,
                        )
                        xml_ar_from_ad = None
                except Exception as exc_ar:
                    logger.warning(
                        'Error parseando ApplicationResponse embebido: %s', exc_ar,
                    )

            # Extraer el Invoice principal
            xpath_factura = (
                './/cac:Attachment/cac:ExternalReference/cbc:Description'
                '[not(ancestor::cac:ParentDocumentLineReference)]'
            )
            nodos = xml_invoice.xpath(xpath_factura, namespaces=ns)
            if nodos and nodos[0].text:
                try:
                    xml_invoice = etree.fromstring(nodos[0].text.strip().encode('utf-8'))
                    tag_local = etree.QName(xml_invoice).localname
                    logger.info(
                        'Invoice extraído del AttachedDocument (adjunto=%s).',
                        adjunto_id,
                    )
                except Exception as exc_parse:
                    logger.error(
                        'Error parseando Invoice embebido del AttachedDocument %s: %s',
                        s3_key, exc_parse,
                    )
                    self._repo.crear_proceso_ingesta(
                        conn, adjunto_id, IdTipoProceso.validacion_cufe,
                        f'Error parseando Invoice embebido: {exc_parse}',
                        IdEstadoProceso.error,
                    )
                    return False
            else:
                logger.warning(
                    'AttachedDocument %s no contiene Invoice embebido.',
                    s3_key,
                )
                self._repo.marcar_evento_procesado(conn, adjunto_id)
                if ar_ev:
                    self._repo.marcar_evento_procesado(conn, ar_ev['adjunto_id'])
                if pdf_ev:
                    self._repo.marcar_evento_procesado(conn, pdf_ev['adjunto_id'])
                return True

        if tag_local != 'Invoice':
            logger.warning(
                'Omitiendo documento %s: no es una factura electrónica (tipo=%s).',
                s3_key, tag_local
            )
            # Marcar todos los eventos de la familia como procesados para limpiarlos de la cola
            self._repo.marcar_evento_procesado(conn, adjunto_id)
            if ar_ev:
                self._repo.marcar_evento_procesado(conn, ar_ev['adjunto_id'])
            if ad_ev:
                self._repo.marcar_evento_procesado(conn, ad_ev['adjunto_id'])
            if pdf_ev:
                self._repo.marcar_evento_procesado(conn, pdf_ev['adjunto_id'])
            return True

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
                logger.debug('CUFE %s ya procesado con mismo SHA256, omitiendo.', cufe[:20])
                self._alert_manager.duplicado_detectado(
                    cufe=cufe, sha256=sha256_actual, adjunto_id=adjunto_id,
                )
                self._repo.marcar_evento_procesado(conn, adjunto_id)
                if ar_ev:
                    self._repo.marcar_evento_procesado(conn, ar_ev['adjunto_id'])
                if ad_ev:
                    self._repo.marcar_evento_procesado(conn, ad_ev['adjunto_id'])
                return True
            logger.debug('CUFE %s existe con SHA256 diferente, reprocesando.', cufe[:20])

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

        res_firma = validar_firma_digital_v1(xml_invoice)
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
        if xml_ar is None and xml_ar_from_ad is not None:
            xml_ar = xml_ar_from_ad
            logger.info('Usando ApplicationResponse embebido del AttachedDocument para validación DIAN.')

        res_dian = validar_documento_validacion_dian_v1(xml_invoice, xml_ar)
        ar_adjunto = ar_ev['adjunto_id'] if ar_ev else adjunto_id
        self._registrar_proceso(conn, ar_adjunto, IdTipoProceso.validacion_documento_dian, res_dian)

        # 6. Validaciones del AttachedDocument (req_06)
        res_fv = None
        if ad_ev:
            xml_ad = obtener_xml_s3(ad_ev['uri_almacenamiento'])
            if xml_ad is not None:
                res_fv = validar_fecha_validacion_dian_v1(xml_ad)
            else:
                res_fv = {'valido': False, 'mensaje': 'No se pudo descargar AttachedDocument.', 'datos': {}}
            self._registrar_proceso(conn, ad_ev['adjunto_id'], IdTipoProceso.validacion_fecha_validacion, res_fv)

        # Determinar si la factura es válida o se rechaza
        validaciones_obligatorias = [
            res_denom, res_emisor, res_adq, res_num, res_fecha,
            res_items, res_valor, res_forma, res_medio, res_fiscal,
            res_imp, res_firma, res_qr, res_anexo, res_sw
        ]
        if ar_ev or xml_ar_from_ad is not None:
            validaciones_obligatorias.append(res_dian)
        if ad_ev:
            validaciones_obligatorias.append(res_fv)

        fallas = [v['mensaje'] for v in validaciones_obligatorias if not v.get('valido', False)]
        if fallas:
            id_estado_factura = IdEstadoProceso.error
        else:
            id_estado_factura = IdEstadoProceso.procesado

        # 7. Poblar tablas de BD
        id_factura = self._poblar_tablas(
            conn, adjunto_id, cufe, res_denom, res_emisor, res_adq,
            res_num, res_fecha, res_valor, res_firma, res_qr,
            res_items, res_imp, res_forma, res_medio, res_fiscal, res_sw,
            res_dian,
            res_fv=res_fv if ad_ev else None,
            id_estado_factura=id_estado_factura,
            fallas=fallas
        )

        # 8. Marcar eventos como procesados
        self._repo.marcar_evento_procesado(conn, adjunto_id)
        if ar_ev:
            self._repo.marcar_evento_procesado(conn, ar_ev['adjunto_id'])
        if ad_ev:
            self._repo.marcar_evento_procesado(conn, ad_ev['adjunto_id'])
        if pdf_ev:
            self._repo.marcar_evento_procesado(conn, pdf_ev['adjunto_id'])

        # Disparar alerta si hubo fallas DIAN
        if fallas:
            motivo_rechazo = "; ".join(fallas)
            nit_proveedor = res_emisor['datos'].get('numero_documento')
            num_factura = res_num['datos'].get('numero_factura') or cufe[:20]
            
            self._alert_manager.factura_rechazada(
                motivo=motivo_rechazo,
                nit=nit_proveedor,
                num_factura=num_factura,
                factura_id=id_factura,
                adjunto_id=adjunto_id,
                correo_id=invoice_ev.get('correo_id')
            )

        # 9. Verificación Gráfica del PDF (si existe, se persistió con éxito y la factura no tiene fallas de validación de XML)
        if pdf_ev and id_factura > 0 and not fallas:
            self._ejecutar_verificacion_grafica(conn, cufe, pdf_ev)

        if fallas:
            logger.warning('Factura rechazada por fallas DIAN (CUFE=%s): %s', cufe[:20], fallas)
        else:
            logger.debug('Factura procesada exitosamente: CUFE=%s', cufe[:20])
        return True

    # ------------------------------------------------------------------
    # Verificación Gráfica y Huérfanos
    # ------------------------------------------------------------------

    def _procesar_pdf_huerfano(self, pdf_ev: dict) -> str:
        """Procesa un evento de tipo PDF huérfano.
        
        Extrae el CUFE usando el LLM, busca la factura, y si la encuentra,
        la vincula y ejecuta la verificación gráfica.
        """
        adjunto_id = pdf_ev['adjunto_id']
        s3_key = pdf_ev['uri_almacenamiento']
        
        with self._repo.get_connection() as conn:
            try:
                # 1. Descargar PDF desde S3 a temporal
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp_path = tmp.name
                    
                exito_descarga = descargar_archivo_s3(s3_key, tmp_path)
                if not exito_descarga:
                    logger.error("No se pudo descargar el PDF huérfano desde S3: %s", s3_key)
                    self._repo.crear_proceso_ingesta(
                        conn, adjunto_id, IdTipoProceso.verificacion_grafica,
                        "No se pudo descargar el PDF desde S3.",
                        IdEstadoProceso.error
                    )
                    conn.commit()
                    return 'fail'

                # 2. Extraer CUFE
                cufe = asyncio.run(extraer_cufe_pdf(tmp_path))
                
                if not cufe:
                    self._repo.crear_proceso_ingesta(
                        conn, adjunto_id, IdTipoProceso.verificacion_grafica,
                        "No se pudo extraer el CUFE del PDF usando el LLM. Queda huérfano permanentemente.",
                        IdEstadoProceso.procesado
                    )
                    self._repo.marcar_evento_procesado(conn, adjunto_id)
                    conn.commit()
                    os.unlink(tmp_path)
                    return 'skip'

                # 3. Vincular a Factura
                vinculado = self._repo.vincular_pdf_a_factura(conn, cufe, adjunto_id)
                if not vinculado:
                    logger.info(
                        "PDF huérfano (adjunto=%s) con CUFE %s no tiene factura "
                        "registrada aún. Se reintentará con cooldown.",
                        adjunto_id, cufe[:20],
                    )
                    os.unlink(tmp_path)
                    return 'retry_later'

                # 4. Ejecutar Verificación Gráfica
                self._ejecutar_verificacion_grafica(conn, cufe, pdf_ev, tmp_path)
                
                # 5. Marcar evento como procesado
                self._repo.marcar_evento_procesado(conn, adjunto_id)
                conn.commit()
                os.unlink(tmp_path)
                return 'ok'

            except Exception as exc:
                conn.rollback()
                logger.exception('Error procesando PDF huérfano: %s', exc)
                self._repo.crear_proceso_ingesta(
                    conn, adjunto_id, IdTipoProceso.verificacion_grafica,
                    f"Error inesperado: {exc}",
                    IdEstadoProceso.error
                )
                conn.commit()
                if 'tmp_path' in locals() and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return 'fail'

    def _ejecutar_verificacion_grafica(
        self, 
        conn, 
        cufe: str, 
        pdf_ev: dict, 
        local_pdf_path: Optional[str] = None
    ):
        """Ejecuta la verificación gráfica de un PDF con la IA."""
        adjunto_id = pdf_ev['adjunto_id']
        s3_key = pdf_ev['uri_almacenamiento']
        tmp_path = local_pdf_path
        borrar_tmp = False

        try:
            if not tmp_path:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp_path = tmp.name
                borrar_tmp = True
                
                exito = descargar_archivo_s3(s3_key, tmp_path)
                if not exito:
                    self._repo.crear_proceso_ingesta(
                        conn, adjunto_id, IdTipoProceso.verificacion_grafica,
                        "Fallo al descargar PDF de S3 para verificación gráfica.",
                        IdEstadoProceso.error
                    )
                    return

            datos_factura = self._repo.obtener_datos_completos_factura(conn, cufe)
            if not datos_factura:
                logger.warning(
                    'No se encontraron datos de factura (CUFE=%s) para verificación gráfica. '
                    'La factura puede no haberse registrado aún.',
                    cufe[:20],
                )
                self._repo.crear_proceso_ingesta(
                    conn, adjunto_id, IdTipoProceso.verificacion_grafica,
                    f'Sin datos de factura en BD (CUFE={cufe[:20]}...). '
                    'Verificación gráfica omitida.',
                    IdEstadoProceso.error,
                )
                return

            factura_id = datos_factura.get('id_factura')
            resultado = asyncio.run(verificar_representacion_grafica(tmp_path, datos_factura, id_factura=factura_id, conn=conn))
            
            aprobado = resultado.get('aprobado', False)
            metodo = resultado.get('metodo', 'DESCONOCIDO')
            observacion = resultado.get('observacion', '')
            campos = resultado.get('campos', {})
            
            if aprobado:
                mensaje = f"Representación gráfica verificada correctamente ({metodo})."
                estado_grafico = 'APROBADA'
                estado_proceso = IdEstadoProceso.procesado
            else:
                mensaje = f"IA detectó discrepancias en el PDF ({metodo}): {observacion}"
                estado_grafico = 'PENDIENTE'
                estado_proceso = IdEstadoProceso.procesado
                
                campos_fallidos = [c for c, info in campos.items() if not (info.get('encontrado') or info.get('presente'))]
                
                self._alert_manager.verificacion_grafica_fallida(
                    num_factura=datos_factura.get('numero_factura', 'DESCONOCIDO'),
                    metodos=[metodo],
                    campos_fallidos={'faltantes': campos_fallidos},
                    adjunto_id=adjunto_id,
                    correo_id=pdf_ev.get('correo_id'),
                    factura_id=factura_id
                )

            if factura_id:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE FACTURACION.FACTURA 
                        SET VERIFICACION_GRAFICA_ESTADO = %s, FECHA_ACTUALIZACION = NOW()
                        WHERE ID_FACTURA = %s
                        """,
                        (estado_grafico, factura_id)
                    )

            self._repo.crear_proceso_ingesta(
                conn, adjunto_id, IdTipoProceso.verificacion_grafica,
                mensaje[:254], estado_proceso
            )
        finally:
            if borrar_tmp and tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning("No se pudo eliminar temporal %s: %s", tmp_path, e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _registrar_proceso(self, conn, adjunto_id: int, tipo: int, resultado: dict) -> None:
        """Registra un paso de validación en PROCESO_INGESTA."""
        valido = resultado.get('valido', False)
        estado = IdEstadoProceso.procesado if valido else IdEstadoProceso.error
        id_error = resultado.get('id_error')

        self._repo.crear_proceso_ingesta(conn, adjunto_id, tipo, resultado['mensaje'], estado, id_error)

    @staticmethod
    def _sanitizar_segmento_ruta(valor: str) -> str:
        """Limpia un valor para usarlo como segmento de path S3.

        Reemplaza separadores y caracteres conflictivos por guiones bajos.
        """
        if not valor:
            return 'DESCONOCIDO'
        seguro = ''.join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in valor)
        return seguro.strip('_') or 'DESCONOCIDO'

    def _obtener_codigo_tipo_documento(self, conn, id_tipo_documento: Optional[str]) -> str:
        """Resuelve el `CODIGO_REFERENCIA` (ej: 'NIT') desde el catálogo.

        Devuelve 'DESCONOCIDO' si el código no está mapeado o es nulo.
        """
        if not id_tipo_documento:
            return 'DESCONOCIDO'
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT CODIGO_REFERENCIA '
                    'FROM FACTURACION.TIPO_DOCUMENTO_IDENTIDAD '
                    'WHERE ID_TIPO_DOCUMENTO = %s',
                    (id_tipo_documento,),
                )
                row = cur.fetchone()
                return row[0] if row else 'DESCONOCIDO'
        except Exception:
            logger.exception(
                'Error consultando TIPO_DOCUMENTO_IDENTIDAD para id=%s',
                id_tipo_documento,
            )
            return 'DESCONOCIDO'

    def _copiar_adjuntos_a_processed(
        self,
        conn,
        adjunto_id: int,
        numero_documento_emisor: str,
        fecha_referencia: datetime,
        id_tipo_documento_emisor: Optional[str] = None,
    ) -> None:
        """Copia los archivos originales de la factura a la zona `processed/` en S3.

        Para una factura recién registrada, busca toda su familia de adjuntos
        (ZIP raíz, sub-ZIPs anidados, XML Invoice original y PDF) y los copia
        server-side dentro del bucket a la ruta:

            quipux/facturacion_electronica/processed/facturas/
                {proveedor}/{year}/{month}/{day}/{nombre_descarga}

        - `proveedor`  = `numero_documento` del emisor identificado en la
          validación de la factura (req_02).
        - `year/month/day` se derivan de la fecha de generación de la factura
          (mismo criterio que `_procesar_zips` usa con `fecha_envio`).

        Solo se copian:
            * Archivos ZIP (raíz y anidados).
            * El XML Invoice original (NO los AttachedDocument ni
              ApplicationResponse, que son XML auxiliares).
            * El PDF.

        Es una operación best-effort: cualquier fallo se loguea pero no
        interrumpe la transacción de registro de la factura.
        """
        adjuntos = self._repo.obtener_adjuntos_familia(conn, adjunto_id)
        if not adjuntos:
            logger.debug(
                'No se encontraron adjuntos en la familia de adjunto_id=%s',
                adjunto_id,
            )
            return

        proveedor = self._sanitizar_segmento_ruta(numero_documento_emisor)
        tipo_documento = self._sanitizar_segmento_ruta(
            self._obtener_codigo_tipo_documento(conn, id_tipo_documento_emisor)
        ).lower()
        year = fecha_referencia.strftime('%Y')
        month = fecha_referencia.strftime('%m')
        day = fecha_referencia.strftime('%d')

        copiados = 0
        for adj in adjuntos:
            id_tipo = adj.get('id_tipo_archivo')
            uri_origen = adj.get('uri_almacenamiento')
            nombre = adj.get('nombre_archivo')

            if not uri_origen or not nombre:
                continue

            # Filtrar: solo ZIP, PDF y el XML Invoice original.
            nombre_lower = nombre.lower()
            nombre_destino = nombre
            if id_tipo == IdTipoArchivo.zip:
                pass
            elif id_tipo == IdTipoArchivo.pdf:
                pass
            elif id_tipo == IdTipoArchivo.xml:
                # Solo copiamos el XML "Invoice" embebido (contiene "_invoice"
                # en el nombre; lo genera _registrar_par_factura). El XML padre
                # original (AttachedDocument, sin sufijo) y el ApplicationResponse
                # son auxiliares y no se copian a processed/.
                idx = nombre_lower.rfind('_invoice')
                if idx == -1:
                    continue
                # Quitar el sufijo "_invoice" del nombre destino, ya que la
                # ruta processed/ no lo necesita.
                nombre_destino = nombre[:idx] + nombre[idx + len('_invoice'):]
            else:
                continue

            destino = RutasS3.factura_procesada_dir.format(
                tipo_documento=tipo_documento,
                proveedor=proveedor, year=year, month=month, day=day,
            ) + '/' + nombre_destino

            ok = copiar_archivo_s3(origen_key=uri_origen, destino_key=destino)
            if ok:
                copiados += 1
            else:
                logger.warning(
                    'No se pudo copiar adjunto a processed: %s -> %s',
                    uri_origen, destino,
                )

        logger.info(
            'Adjuntos copiados a processed/ para adjunto_id=%s proveedor=%s: %d',
            adjunto_id, proveedor, copiados,
        )

    def _poblar_tablas(self, conn, adjunto_id, cufe, res_denom, res_emisor,
                       res_adq, res_num, res_fecha, res_valor, res_firma,
                       res_qr, res_items, res_imp, res_forma, res_medio,
                       res_fiscal, res_sw, res_dian, res_fv=None,
                       id_estado_factura=None, fallas=None) -> int:
        """Puebla las tablas de facturación con los datos validados."""
        try:
            # TERCERO emisor
            datos_emisor = res_emisor['datos']
            id_emisor = self._repo.upsert_tercero(conn, {
                'id_rol_tercero': 1,  # EMISOR
                'numero_documento': datos_emisor.get('numero_documento') or 'DESCONOCIDO',
                'digito_verificador': datos_emisor.get('digito_verificador'),
                'correo_contacto': datos_emisor.get('correo_contacto'),
                'telefono_contacto': datos_emisor.get('telefono_contacto'),
                'id_tipo_documento': datos_emisor.get('scheme_name'),
            })

            # TERCERO adquiriente
            datos_adq = res_adq['datos']
            id_adq = self._repo.upsert_tercero(conn, {
                'id_rol_tercero': 2,  # ADQUIRIENTE
                'numero_documento': datos_adq.get('numero_documento') or 'DESCONOCIDO',
                'digito_verificador': datos_adq.get('digito_verificador'),
                'correo_contacto': datos_adq.get('correo_contacto'),
                'telefono_contacto': datos_adq.get('telefono_contacto'),
                'id_tipo_documento': datos_adq.get('scheme_name'),
            })

            # AUTORIZACION_NUMERACION_DIAN
            id_autorizacion = None
            datos_num = res_num['datos']
            if datos_num.get('numero_autorizacion'):
                fecha_inicio = datos_num.get('fecha_inicio_vigencia')
                fecha_fin = datos_num.get('fecha_fin_vigencia')
                id_autorizacion = self._repo.upsert_autorizacion(conn, {
                    'id_tercero_emisor': id_emisor,
                    'numero_resolucion': datos_num['numero_autorizacion'],
                    'prefijo_facturacion': datos_num.get('prefijo') or '',
                    'rango_desde': datos_num.get('rango_desde') or 0,
                    'rango_hasta': datos_num.get('rango_hasta') or 0,
                    'fecha_autorizacion': fecha_inicio,
                    'fecha_inicio_vigencia': fecha_inicio,
                    'fecha_fin_vigencia': fecha_fin,
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
            
            nombre_proveedor = datos_emisor.get('razon_social') or datos_emisor.get('nombre_comercial')
            nit_proveedor = datos_emisor.get('numero_documento')
            forma_pago_desc = "CREDITO" if d_pago.get('codigo_forma_pago') == '2' else "CONTADO"

            id_factura = self._repo.insertar_factura(conn, {
                'cufe': cufe,
                'denominacion': d_denom.get('denominacion'),
                'codigo_tipo_documento_dian': d_denom.get('codigo_tipo_documento'),
                'prefijo': datos_num.get('prefijo') or '',
                'numero_factura': datos_num.get('numero_factura') or cufe[:20],
                'id_tercero_emisor': id_emisor,
                'razon_social_emisor': nombre_proveedor,
                'id_tercero_adquiriente': id_adq,
                'razon_social_adquiriente': datos_adq.get('razon_social') or datos_adq.get('nombre_comercial'),
                'id_autorizacion': id_autorizacion,
                'fecha_generacion': fecha_gen,
                'fecha_expedicion': fecha_gen,
                'fecha_vencimiento': d_pago.get('fecha_vencimiento'),
                'moneda': d_valor.get('moneda') or 'COP',
                'valor_total': valor_total,
                'hash_firma': d_firma.get('hash_firma_digital'),
                'contenido_qr': d_qr.get('contenido_qr'),
                'adjunto_id': adjunto_id,
                'id_estado_proceso': id_estado_factura if id_estado_factura is not None else IdEstadoProceso.procesado,
            })

            if id_factura <= 0:
                logger.error('No se pudo insertar la factura CUFE=%s', cufe[:20])
                return 0

            # Insertar en FACTURA_CONTROL
            self._repo.upsert_factura_control(conn, {
                'id_factura': id_factura,
                'fecha_admision_proveedor': fecha_gen.date() if fecha_gen else None,
                'medio_recepcion': 'CORREO',
                'nombre_proveedor': nombre_proveedor,
                'nit_proveedor': nit_proveedor,
                'numero_factura': datos_num.get('numero_factura'),
                'forma_pago': forma_pago_desc
            })

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

            # SOFTWARE
            d_sw = res_sw['datos']
            nit_proveedor = d_sw.get('nit_proveedor')
            nombre_proveedor = d_sw.get('nombre_proveedor')
            id_software = d_sw.get('id_software')
            
            if nit_proveedor or nombre_proveedor or id_software:
                id_fabricante = self._repo.insertar_fabricante_software(
                    conn,
                    numero_documento=nit_proveedor or 'DESCONOCIDO',
                    razon_social=nombre_proveedor or 'Desconocido',
                )
                if id_software:
                    id_producto = self._repo.insertar_producto_software(
                        conn, id_fabricante, id_software
                    )
                    if id_producto > 0:
                        nit_pt = nit_proveedor if d_sw.get('es_autorizado') else None
                        self._repo.insertar_software_factura(
                            conn, id_factura, id_producto, nit_pt
                        )

            # EVENTO_DIAN_FACTURA
            d_dian = res_dian['datos']
            codigo_evento = d_dian.get('codigo_evento')
            if codigo_evento:
                self._repo.insertar_evento_dian_factura(
                    conn,
                    id_factura=id_factura,
                    codigo_evento=codigo_evento,
                    descripcion=d_dian.get('descripcion_respuesta'),
                    id_rastreo=d_dian.get('id_rastreo'),
                )

            try:
                self._copiar_adjuntos_a_processed(
                    conn=conn,
                    adjunto_id=adjunto_id,
                    numero_documento_emisor=(
                        datos_emisor.get('numero_documento') or 'DESCONOCIDO'
                    ),
                    fecha_referencia=fecha_gen,
                    id_tipo_documento_emisor=datos_emisor.get('scheme_name'),
                )
            except Exception as exc_copia:
                logger.warning(
                    'Fallo al copiar adjuntos a processed/ para CUFE=%s: %s',
                    cufe[:20], exc_copia,
                )

            # Registro final
            obs = f'Factura registrada: ID={id_factura}, CUFE={cufe[:20]}...'
            est = IdEstadoProceso.procesado
            if fallas:
                obs = f'Factura rechazada por fallas DIAN: {"; ".join(fallas)}'
                est = IdEstadoProceso.error
            self._repo.crear_proceso_ingesta(
                conn, adjunto_id, IdTipoProceso.registro_factura,
                obs[:254],
                est,
            )
            return id_factura

        except Exception as exc:
            logger.exception('Error poblando tablas para CUFE=%s: %s', cufe[:20], exc)
            self._repo.crear_proceso_ingesta(
                conn, adjunto_id, IdTipoProceso.registro_factura,
                f'Error al registrar factura: {exc}'[:254],
                IdEstadoProceso.error,
            )
            return 0

    def _manejar_error_evento(self, conn, evento: dict, error: str) -> None:
        """Maneja errores incrementando intentos o marcando como fallido."""
        try:
            intentos = self._repo.incrementar_intentos_evento(conn, evento['adjunto_id'])
            if intentos >= self._max_reintentos:
                self._repo.actualizar_estado_evento(
                    conn, evento['adjunto_id'], IdEstadoProceso.fallido
                )
                self._repo.crear_proceso_ingesta(
                    conn, evento['adjunto_id'], IdTipoProceso.registro_factura,
                    f'Máximo de reintentos ({self._max_reintentos}) excedido: {error}',
                    IdEstadoProceso.fallido,
                )
                self._alert_manager.max_reintentos_excedido(
                    adjunto_id=evento['adjunto_id'],
                    cufe=evento.get('cufe'),
                    intentos=intentos,
                    error=error,
                    conn=conn,
                )
            else:
                self._repo.actualizar_estado_evento(
                    conn, evento['adjunto_id'], IdEstadoProceso.pendiente
                )
        except Exception:
            logger.exception('Error manejando fallo del evento %s', evento.get('adjunto_id'))


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
