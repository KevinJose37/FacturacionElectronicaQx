"""Listener de correos IMAP para ingesta de facturas electrónicas."""

from __future__ import annotations
 
import asyncio
import email as _email
import imaplib
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional
 
import yaml
from dotenv import load_dotenv
 
from config import get_postgres_config
from core.python.ingesta.queue_publisher import get_publisher
from core.python.rechazos.rechazo_handler import RechazoHandler
from core.python.utils.xml_utils import extraer_xmls_embebidos
from metadata.db_metadata import (
    IdEstadoProceso,
    IdTipoArchivo,
    IdTipoError,
    IdTipoProceso,
)
from utils.alerts import AlertManager
from utils.attachment_handler import AdjuntoDescargado, AttachmentHandler
from utils.attachment_validator import AttachmentValidator, ParXmlPdf
from utils.email_parser import EmailParser
from utils.email_repository import EmailRepository
from utils.factura_filter import FacturaFilter
from utils.malware_scanner import MalwareScanner
from utils.s3_utils import subir_archivo_s3

load_dotenv()

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "settings.yaml"


def _load_config() -> dict:
    """Carga la configuración desde el archivo YAML."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuración no encontrada en {_CONFIG_PATH}")
    with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
        
    # Permitir sobreescribir el nivel de log por variable de entorno
    env_log_level = os.environ.get('LOG_LEVEL')
    if env_log_level and 'logging' in config:
        config['logging']['level'] = env_log_level.upper()
        
    return config


_CONFIG = _load_config()

# Configurar logging global basado en la configuración cargada
log_level_str = _CONFIG.get('logging', {}).get('level', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level_str, logging.INFO),
    format=_CONFIG.get('logging', {}).get('format', "%(asctime)s [%(levelname)s] %(name)s - %(message)s")
)

logger = logging.getLogger(__name__)


class EmailListener:
    """Listener IMAP para procesamiento de facturas con flujo completo."""

    def __init__(self):
        """Inicializa el listener con configuración y dependencias."""
        email_cfg = _CONFIG["email"]
        retry_cfg = _CONFIG.get("retry", {})

        self.host = email_cfg["host"]
        self.port = int(email_cfg["port"])
        self.usuario = os.environ["EMAIL_USER"]
        self.carpeta = email_cfg["carpeta"]
        self.max_attempts = int(retry_cfg.get("max_attempts", 3))
        self.backoff_base = float(retry_cfg.get("backoff_base_seconds", 2))
        self.poll_interval = int(_CONFIG.get("poll_interval_seconds", 60))
        self.id_origen = int(_CONFIG.get("id_origen", 1))

        self._password = os.environ["EMAIL_PASSWORD"]
        self._parser = EmailParser()
        self._attachment_handler = AttachmentHandler(_CONFIG)
        self._validator = AttachmentValidator(temp_dir=_CONFIG.get("validations", {}).get("temp_dir", "temp"))
        self._scanner = MalwareScanner(_CONFIG.get("security", {}))
        self._repository = EmailRepository(get_postgres_config())
        self._alert_manager = AlertManager(_CONFIG)
        self._publisher = get_publisher(_CONFIG)

    def _conectar(self) -> imaplib.IMAP4_SSL:
        """Establece conexión IMAP con reintentos."""
        for intento in range(1, self.max_attempts + 1):
            try:
                conn = imaplib.IMAP4_SSL(self.host, self.port)
                conn.login(self.usuario, self._password)
                conn.select(self.carpeta)
                logger.info("Conexión IMAP establecida")
                return conn
            except (imaplib.IMAP4.error, OSError) as exc:
                if intento == self.max_attempts:
                    self._alert_manager.error_conexion("IMAP", str(exc))
                    raise ConnectionError(f"Falla conexión IMAP: {exc}")
                logger.warning("Intento %d/%d fallido: %s", intento, self.max_attempts, exc)
                time.sleep(self.backoff_base**intento)

    def _obtener_uids(self, conn: imaplib.IMAP4_SSL) -> list:
        """Obtiene UIDs de correos no leídos."""
        status, data = conn.uid("search", None, "UNSEEN")
        uids = data[0].split() if status == "OK" else []
        logger.info("Correos no leídos encontrados: %d", len(uids))
        return uids

    def _extraer_id_mensaje(self, msg: _email.message.Message) -> str:
        """Extrae el Message-ID del correo."""
        message_id = msg.get("Message-ID", "")
        if message_id.startswith("<") and message_id.endswith(">"):
            message_id = message_id[1:-1]
        return message_id or f"unknown-{datetime.now(tz=timezone.utc).timestamp()}"

    # ------------------------------------------------------------------
    # Helpers de procesamiento de adjuntos
    # ------------------------------------------------------------------

    def _escanear_archivo(self, ruta: Path) -> 'ScanResult':
        """Escanea un archivo individual contra malware.

        Returns:
            ScanResult con el veredicto de seguridad.
        """
        scan = self._scanner.escanear_archivo(ruta)
        if not scan.seguro:
            if not scan.servicio_disponible:
                logger.error("Error de disponibilidad en escáner para %s: %s", ruta.name, scan.detalle)
                # No lanzamos alerta de malware porque es un error de infraestructura
            else:
                self._alert_manager.malware_detectado(ruta.name, scan.nivel_riesgo)
                logger.critical("Malware detectado en %s: %s", ruta, scan.detalle)
        return scan

    def _procesar_zips(
        self,
        zips: list,
        conn_db,
        id_correo: int,
        id_mensaje: str,
        fecha_envio: Optional[datetime],
        parsed: dict,
    ) -> list:
        """Procesa una lista de adjuntos ZIP, extrae pares XML+PDF.

        Soporta ZIPs con contenido directo y ZIPs con sub-ZIPs anidados.

        Returns:
            Lista de diccionarios con info de cada par procesado exitosamente.
        """
        resultados = []

        for adj_zip in zips:
            # Verificar hash duplicado — si el mismo archivo ya fue procesado, omitir.
            # Las correcciones de factura tienen contenido distinto → hash diferente → se procesan.
            sha256_zip = self._repository.calcular_hash_sha256(adj_zip.ruta)
            if self._repository.existe_adjunto_por_hash(conn_db, sha256_zip):
                logger.debug(
                    "ZIP con hash ya existente en BD (hash=%s): %s. Omitiendo duplicado.",
                    sha256_zip[:8], adj_zip.nombre_original,
                )
                continue

            # Escanear el ZIP
            try:
                scan_zip = self._escanear_archivo(adj_zip.ruta)
                if not scan_zip.seguro:
                    if not scan_zip.servicio_disponible:
                        raise ConnectionError(f"Servicio de seguridad no disponible durante escaneo de ZIP: {scan_zip.detalle}")
                    
                    logger.critical("ZIP infectado: %s", adj_zip.nombre_original)
                    # Registrar ZIP infectado en BD para trazabilidad
                    id_zip_infectado, _ = self._repository.guardar_adjunto_correo(
                        conn=conn_db, id_correo=id_correo, ruta_archivo=adj_zip.ruta,
                        id_tipo_archivo=IdTipoArchivo.zip, archivo_seguro=False,
                        fecha_envio=fecha_envio,
                    )
                    if id_zip_infectado != -1:
                        self._repository.crear_proceso_ingesta(
                            conn=conn_db, adjunto_id=id_zip_infectado,
                            id_proceso=IdTipoProceso.escaneo_malware,
                            observacion=f"ZIP rechazado: {scan_zip.detalle}",
                            id_estado=IdEstadoProceso.procesado,
                            id_error=IdTipoError.malware_detectado,
                        )
                    continue
            except ConnectionError:
                # Registrar el fallo de infraestructura a nivel de correo antes de re-lanzar
                self._repository.crear_proceso_ingesta(
                    conn=conn_db, 
                    id_proceso=IdTipoProceso.escaneo_malware,
                    observacion="Falla de infraestructura: ClamAV no disponible",
                    id_estado=IdEstadoProceso.error,
                    correo_id=id_correo,
                    id_error=IdTipoError.conexion_fallida if hasattr(IdTipoError, 'conexion_fallida') else None
                )
                conn_db.commit()
                raise

            # Validar contenido (con soporte para ZIPs anidados)
            validacion = self._validator.validar_zip_completo(adj_zip.ruta)
            # Registrar el ZIP padre en ADJUNTOS_CORREO
            id_adjunto_zip, uri_zip = self._repository.guardar_adjunto_correo(
                conn=conn_db,
                id_correo=id_correo,
                ruta_archivo=adj_zip.ruta,
                id_tipo_archivo=IdTipoArchivo.zip,
                archivo_seguro=True,
                fecha_envio=fecha_envio,
            )
            if id_adjunto_zip == -1:
                logger.error("No se pudo registrar ZIP en BD: %s", adj_zip.nombre_original)
                continue

            # Subir a S3
            subir_archivo_s3(adj_zip.ruta, uri_zip)

            if not validacion.es_valido or not validacion.pares:
                self._alert_manager.adjunto_incompleto(
                    email_uid=id_mensaje,
                    archivos=validacion.archivos_encontrados,
                    motivo=validacion.motivo_error or "ZIP sin pares XML+PDF válidos",
                )
                logger.error(
                    "Validación ZIP falló: %s | %s",
                    adj_zip.nombre_original, validacion.motivo_error,
                )
                self._repository.crear_proceso_ingesta(
                    conn=conn_db, adjunto_id=id_adjunto_zip,
                    id_proceso=IdTipoProceso.validacion_contenido_zip,
                    observacion=f"ZIP rechazado: {validacion.motivo_error}",
                    id_estado=IdEstadoProceso.error,
                    id_error=validacion.id_error or IdTipoError.zip_corrupto,
                )
                continue

            # Si hay ZIPs anidados, registrarlos también
            zips_anidados_ids = {}
            if validacion.tiene_zips_anidados:
                for par in validacion.pares:
                    if par.zip_origen and par.zip_origen != adj_zip.ruta:
                        sub_zip_key = str(par.zip_origen)
                        if sub_zip_key not in zips_anidados_ids:
                            id_sub_zip, uri_sub_zip = self._repository.guardar_adjunto_correo(
                                conn=conn_db,
                                id_correo=id_correo,
                                ruta_archivo=par.zip_origen,
                                id_tipo_archivo=IdTipoArchivo.zip,
                                adjunto_padre_id=id_adjunto_zip,
                                archivo_seguro=True,
                                fecha_envio=fecha_envio,
                            )
                            if id_sub_zip != -1:
                                subir_archivo_s3(par.zip_origen, uri_sub_zip)
                                zips_anidados_ids[sub_zip_key] = id_sub_zip

            # Procesar cada par XML+PDF
            for par in validacion.pares:
                resultado = self._registrar_par_factura(
                    par=par,
                    conn_db=conn_db,
                    id_correo=id_correo,
                    id_adjunto_padre=zips_anidados_ids.get(str(par.zip_origen), id_adjunto_zip),
                    fecha_envio=fecha_envio,
                    parsed=parsed,
                    id_mensaje=id_mensaje,
                )
                if resultado:
                    resultados.append(resultado)

            # Procesar PDFs huérfanos
            for pdf_huerfano in validacion.pdfs_huerfanos:
                resultado_huerfano = self._registrar_pdf_huerfano(
                    pdf_path=pdf_huerfano,
                    conn_db=conn_db,
                    id_correo=id_correo,
                    id_adjunto_padre=zips_anidados_ids.get(str(validacion.pares[0].zip_origen if validacion.pares else adj_zip.ruta), id_adjunto_zip),
                    fecha_envio=fecha_envio,
                    id_mensaje=id_mensaje,
                )
                if resultado_huerfano:
                    resultados.append(resultado_huerfano)

        return resultados

    def _procesar_sueltos(
        self,
        xmls: list,
        pdfs: list,
        conn_db,
        id_correo: int,
        id_mensaje: str,
        fecha_envio: Optional[datetime],
        parsed: dict,
    ) -> list:
        """Procesa archivos XML y PDF adjuntos directamente al correo (sin ZIP).

        Returns:
            Lista de diccionarios con info de cada par procesado exitosamente.
        """
        pares, pdfs_huerfanos = self._validator.agrupar_pares_sueltos(
            xmls=[a.ruta for a in xmls],
            pdfs=[a.ruta for a in pdfs],
        )

        if not pares and not pdfs_huerfanos:
            self._alert_manager.adjunto_incompleto(
                email_uid=id_mensaje,
                archivos=[a.nombre_original for a in xmls + pdfs],
                motivo="No se pudieron emparejar archivos XML y PDF sueltos",
            )
            return []

        resultados = []
        for par in pares:
            resultado = self._registrar_par_factura(
                par=par,
                conn_db=conn_db,
                id_correo=id_correo,
                id_adjunto_padre=None,
                fecha_envio=fecha_envio,
                parsed=parsed,
                id_mensaje=id_mensaje,
            )
            if resultado:
                resultados.append(resultado)

        for pdf_huerfano in pdfs_huerfanos:
            resultado_huerfano = self._registrar_pdf_huerfano(
                pdf_path=pdf_huerfano,
                conn_db=conn_db,
                id_correo=id_correo,
                id_adjunto_padre=None,
                fecha_envio=fecha_envio,
                id_mensaje=id_mensaje,
            )
            if resultado_huerfano:
                resultados.append(resultado_huerfano)

        return resultados

    def _registrar_pdf_huerfano(
        self,
        pdf_path: Path,
        conn_db,
        id_correo: int,
        id_adjunto_padre: Optional[int],
        fecha_envio: Optional[datetime],
        id_mensaje: str,
    ) -> Optional[dict]:
        """Registra un PDF huérfano en BD y S3, y retorna datos para encolar."""
        # 1. Escanear
        scan_pdf = self._escanear_archivo(pdf_path)
        if not scan_pdf.seguro:
            id_pdf_infectado, _ = self._repository.guardar_adjunto_correo(
                conn=conn_db, id_correo=id_correo, ruta_archivo=pdf_path,
                id_tipo_archivo=IdTipoArchivo.pdf, adjunto_padre_id=id_adjunto_padre,
                archivo_seguro=False, fecha_envio=fecha_envio,
            )
            if id_pdf_infectado != -1:
                self._repository.crear_proceso_ingesta(
                    conn=conn_db, adjunto_id=id_pdf_infectado,
                    id_proceso=IdTipoProceso.escaneo_malware,
                    observacion=f"PDF huérfano rechazado: {scan_pdf.detalle}",
                    id_estado=IdEstadoProceso.procesado,
                    id_error=IdTipoError.malware_detectado,
                )
            return None

        # 2. Registrar en BD
        id_adjunto_pdf, uri_pdf = self._repository.guardar_adjunto_correo(
            conn=conn_db, id_correo=id_correo, ruta_archivo=pdf_path,
            id_tipo_archivo=IdTipoArchivo.pdf, adjunto_padre_id=id_adjunto_padre,
            archivo_seguro=True, fecha_envio=fecha_envio,
        )
        if id_adjunto_pdf == -1:
            logger.error("Error registrando PDF huérfano en BD para correo %s", id_mensaje)
            return None

        # Subir a S3
        subir_archivo_s3(pdf_path, uri_pdf)

        # 3. Crear EVENTO_INGESTA
        self._repository.crear_evento_ingesta(conn=conn_db, adjunto_id=id_adjunto_pdf)

        self._repository.crear_proceso_ingesta(
            conn=conn_db, adjunto_id=id_adjunto_pdf,
            id_proceso=IdTipoProceso.escaneo_malware,
            observacion="Escaneo malware exitoso.",
            id_estado=IdEstadoProceso.procesado,
        )

        self._repository.crear_proceso_ingesta(
            conn=conn_db, adjunto_id=id_adjunto_pdf,
            id_proceso=IdTipoProceso.descarga_almacenamiento,
            observacion="PDF huérfano subido correctamente a S3.",
            id_estado=IdEstadoProceso.procesado,
        )

        return {
            "id_adjunto_pdf": id_adjunto_pdf,
            "ruta_pdf": uri_pdf,
            "pdf_huerfano": True,
        }

    def _registrar_par_factura(
        self,
        par: ParXmlPdf,
        conn_db,
        id_correo: int,
        id_adjunto_padre: Optional[int],
        fecha_envio: Optional[datetime],
        parsed: dict,
        id_mensaje: str,
    ) -> Optional[dict]:
        """Registra una factura (XML obligatorio, PDF opcional) en BD.

        Para cada factura:
        1. Escanea XML (y PDF si existe) contra malware
        2. Mueve archivos a ubicación permanente
        3. Registra en ADJUNTOS_CORREO
        4. Crea EVENTO_INGESTA
        5. Registra procesos en PROCESO_INGESTA

        Si el PDF no existe, se registra una observación para revisión humana.

        Returns:
            dict con IDs registrados, o None si el XML falló.
        """
        # 1. Escanear malware — XML es obligatorio
        scan_xml = self._escanear_archivo(par.xml_path)
        if not scan_xml.seguro:
            if not scan_xml.servicio_disponible:
                raise ConnectionError(f"Servicio de seguridad no disponible durante escaneo de XML: {scan_xml.detalle}")
            
            id_xml_infectado, _ = self._repository.guardar_adjunto_correo(
                conn=conn_db, id_correo=id_correo, ruta_archivo=par.xml_path,
                id_tipo_archivo=IdTipoArchivo.xml, adjunto_padre_id=id_adjunto_padre,
                archivo_seguro=False, fecha_envio=fecha_envio,
            )
            if id_xml_infectado != -1:
                self._repository.crear_proceso_ingesta(
                    conn=conn_db, adjunto_id=id_xml_infectado,
                    id_proceso=IdTipoProceso.escaneo_malware,
                    observacion=f"XML rechazado: {scan_xml.detalle}",
                    id_estado=IdEstadoProceso.procesado,
                    id_error=IdTipoError.malware_detectado,
                )
            return None

        if par.pdf_path:
            scan_pdf = self._escanear_archivo(par.pdf_path)
            if not scan_pdf.seguro:
                if not scan_pdf.servicio_disponible:
                    raise ConnectionError(f"Servicio de seguridad no disponible durante escaneo de PDF: {scan_pdf.detalle}")
                
                id_pdf_infectado, _ = self._repository.guardar_adjunto_correo(
                    conn=conn_db, id_correo=id_correo, ruta_archivo=par.pdf_path,
                    id_tipo_archivo=IdTipoArchivo.pdf, adjunto_padre_id=id_adjunto_padre,
                    archivo_seguro=False, fecha_envio=fecha_envio,
                )
                if id_pdf_infectado != -1:
                    self._repository.crear_proceso_ingesta(
                        conn=conn_db, adjunto_id=id_pdf_infectado,
                        id_proceso=IdTipoProceso.escaneo_malware,
                        observacion=f"PDF rechazado: {scan_pdf.detalle}",
                        id_estado=IdEstadoProceso.procesado,
                        id_error=IdTipoError.malware_detectado,
                    )
                # PDF infectado, pero el XML se puede procesar
                par.pdf_path = None
                par.pdf_faltante = True

        # 3. Registrar adjuntos en BD y S3 (XML Padre y PDF)
        id_adjunto_xml, uri_xml = self._repository.guardar_adjunto_correo(
            conn=conn_db, id_correo=id_correo, ruta_archivo=par.xml_path,
            id_tipo_archivo=IdTipoArchivo.xml, adjunto_padre_id=id_adjunto_padre,
            archivo_seguro=True, fecha_envio=fecha_envio,
        )
        if id_adjunto_xml == -1:
            logger.error("Error registrando XML en BD para correo %s", id_mensaje)
            return None

        # Subir XML Padre a S3
        subir_archivo_s3(par.xml_path, uri_xml)

        id_adjunto_pdf = None
        uri_pdf = None
        if par.pdf_path:
            id_adjunto_pdf, uri_pdf = self._repository.guardar_adjunto_correo(
                conn=conn_db, id_correo=id_correo, ruta_archivo=par.pdf_path,
                id_tipo_archivo=IdTipoArchivo.pdf, adjunto_padre_id=id_adjunto_padre,
                archivo_seguro=True, fecha_envio=fecha_envio,
            )
            if id_adjunto_pdf != -1:
                subir_archivo_s3(par.pdf_path, uri_pdf)
                # Crear EVENTO_INGESTA para el PDF: permite que invoice_processor
                # lo incluya en la familia y ejecute la verificación gráfica LLM.
                self._repository.crear_evento_ingesta(conn=conn_db, adjunto_id=id_adjunto_pdf)

        # 4. Crear evento de ingesta para XML padre
        self._repository.crear_evento_ingesta(conn=conn_db, adjunto_id=id_adjunto_xml)

        # 5. Extraer XMLs embebidos y generar eventos
        contenidos_xml = extraer_xmls_embebidos(par.xml_path)
        if isinstance(contenidos_xml, dict):
            for tipo, contenido in contenidos_xml.items():
                if contenido:
                    tmp_path = par.xml_path.with_name(f"{par.xml_path.stem}_{tipo}.xml")
                    tmp_path.write_bytes(contenido)
                    
                    id_embebido, uri_embebido = self._repository.guardar_adjunto_correo(
                        conn=conn_db, id_correo=id_correo, ruta_archivo=tmp_path,
                        id_tipo_archivo=IdTipoArchivo.xml, adjunto_padre_id=id_adjunto_xml,
                        archivo_seguro=True, fecha_envio=fecha_envio,
                    )
                    if id_embebido != -1:
                        subir_archivo_s3(tmp_path, uri_embebido)
                        self._repository.crear_evento_ingesta(conn=conn_db, adjunto_id=id_embebido)
        else:
            logger.warning('No se extrajeron XMLs embebidos de %s: %s', par.xml_path.name, contenidos_xml)

        # 6. Registrar procesos de ingesta realizados
        obs_malware = "Escaneo malware exitoso."
        if par.pdf_faltante:
            obs_malware += " (PDF faltante)"

        self._repository.crear_proceso_ingesta(
            conn=conn_db, adjunto_id=id_adjunto_xml,
            id_proceso=IdTipoProceso.escaneo_malware,
            observacion=obs_malware,
            id_estado=IdEstadoProceso.procesado,
        )

        obs_descarga = "XML subido correctamente a S3."
        if not uri_pdf:
            obs_descarga += " (PDF faltante)"

        self._repository.crear_proceso_ingesta(
            conn=conn_db, adjunto_id=id_adjunto_xml,
            id_proceso=IdTipoProceso.descarga_almacenamiento,
            observacion=obs_descarga,
            id_estado=IdEstadoProceso.procesado,
        )

        if par.zip_origen:
            obs_zip = "ZIP validado exitosamente."
            self._repository.crear_proceso_ingesta(
                conn=conn_db, adjunto_id=id_adjunto_xml,
                id_proceso=IdTipoProceso.validacion_contenido_zip,
                observacion=obs_zip,
                id_estado=IdEstadoProceso.procesado,
            )

        return {
            "id_adjunto_xml": id_adjunto_xml,
            "id_adjunto_pdf": id_adjunto_pdf,
            "ruta_xml": uri_xml,
            "ruta_pdf": uri_pdf if uri_pdf else None,
            "pdf_faltante": par.pdf_faltante,
        }

    # ------------------------------------------------------------------
    # Procesamiento principal
    # ------------------------------------------------------------------

    def _procesar_correo(self, conn: imaplib.IMAP4_SSL, uid: bytes) -> bool:
        """Procesa un correo individual con flujo completo."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir_str:
                # Instanciar manejador de adjuntos para este correo en temp
                old_handler = self._attachment_handler
                self._attachment_handler = AttachmentHandler(_CONFIG, temp_dir=temp_dir_str)
                old_temp_root = self._validator.temp_root
                self._validator.temp_root = Path(temp_dir_str)
                
                try:
                    # 1. FETCH del correo sin marcarlo como leído (PEEK)
                    status, data = conn.uid("fetch", uid, "(BODY.PEEK[])")
                    if status != "OK" or not data:
                        logger.error("No se pudo obtener correo UID=%s", uid)
                        return False

                    raw = data[0][1]
                    msg = _email.message_from_bytes(raw)

                    # 2. Extraer metadata básica
                    id_mensaje = self._extraer_id_mensaje(msg)
                    remitente = msg.get("From", "")
                    asunto = msg.get("Subject", "")
                    fecha_envio_raw = msg.get("Date", None)
                    fecha_envio = None

                    if fecha_envio_raw:
                        try:
                            fecha_envio = parsedate_to_datetime(fecha_envio_raw)
                        except Exception as e:
                            logger.debug("No se pudo parsear fecha de envío: %s | error: %s", fecha_envio_raw, e)

                    # 3. Parsear asunto
                    parsed = self._parser.parsear(asunto)

                    # 3.2 Extraer cuerpos y verificar adjuntos
                    cuerpo_texto, cuerpo_html = self._parser.extraer_cuerpos_mensaje(msg)
                    tiene_adjuntos = any(part.get_filename() for part in msg.walk())

                    # 3.1 Identificar si es facturación (Filtro inicial)
                    filtro = FacturaFilter(_CONFIG)
                    if not filtro.es_facturacion(parsed):
                        logger.info("Correo ignorado (no es facturación): %s - Asunto: %s", id_mensaje, asunto)
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        return True

                    # 4. Verificar adjuntos válidos (ZIP, XML o PDF)
                    tiene_adjuntos_factura = self._attachment_handler.tiene_adjuntos_factura(raw)

                    # 5. Procesamiento principal con transacción
                    with self._repository._get_connection() as conn_db:
                        # 5a. Guardar correo en BD
                        id_correo, es_correo_nuevo = self._repository.guardar_correo_entrante(
                            conn=conn_db,
                            id_mensaje=id_mensaje,
                            remitente=remitente,
                            asunto=asunto,
                            fecha_deteccion=datetime.now(tz=timezone.utc),
                            fecha_envio=fecha_envio,
                            cuerpo_texto=cuerpo_texto,
                            cuerpo_html=cuerpo_html,
                            contiene_adjuntos=tiene_adjuntos,
                            id_origen=self.id_origen,
                        )
                        if not es_correo_nuevo:
                            # El correo ya está en BD. Verificar si fue procesado
                            # completamente (tiene adjuntos exitosos) o si falló a
                            # mitad de camino (ej: ClamAV caído → sin adjuntos).
                            tiene_adjuntos = (
                                id_correo
                                and self._repository.correo_tiene_adjuntos_exitosos(
                                    conn_db, id_correo
                                )
                            )
                            if tiene_adjuntos:
                                # Duplicado real: correo ya procesado exitosamente.
                                self._repository.crear_proceso_ingesta(
                                    conn=conn_db,
                                    id_proceso=IdTipoProceso.filtro_recepcion,
                                    observacion="Correo duplicado: ya fue registrado y procesado anteriormente.",
                                    id_estado=IdEstadoProceso.procesado,
                                    correo_id=id_correo,
                                )
                                conn_db.commit()
                                logger.info(
                                    "Correo ya procesado (ID=%s): %s. Marcando como leído.",
                                    id_correo, id_mensaje,
                                )
                                conn.uid("store", uid, "+FLAGS", "\\Seen")
                                return True
                            else:
                                # Correo en BD pero sin adjuntos exitosos → falló antes.
                                # Continuar con el procesamiento normal (reintento).
                                logger.info(
                                    "Correo ya en BD (ID=%s) pero sin adjuntos exitosos "
                                    "(posible fallo previo). Reintentando procesamiento.",
                                    id_correo,
                                )

                        # 5b. Aplicar filtro de facturación
                        resultado_filtro = filtro.evaluar(parsed, tiene_adjuntos_factura, remitente)

                        if not resultado_filtro.es_factura:
                            motivo = resultado_filtro.motivo_rechazo

                            if motivo == "SIN_ADJUNTOS_FACTURA":
                                obs_rechazo = (
                                    "Correo sin adjuntos válidos de facturación (ZIP/XML)."
                                )
                                id_error_rechazo = IdTipoError.correo_sin_adjuntos_validos
                            else:
                                obs_rechazo = f"Rechazado por filtro: {motivo}"
                                id_error_rechazo = IdTipoError.correo_rechazado_filtro

                            # Registrar en PROCESO_INGESTA (usa correo_id, no adjunto_id)
                            self._repository.crear_proceso_ingesta(
                                conn=conn_db,
                                id_proceso=IdTipoProceso.filtro_recepcion,
                                observacion=obs_rechazo,
                                id_estado=IdEstadoProceso.error,
                                correo_id=id_correo,
                                id_error=id_error_rechazo,
                            )

                            # Commit ANTES de llamar handlers externos
                            # (usan conexiones/pools separados que no ven datos sin commit)
                            conn_db.commit()

                            if motivo == "SIN_ADJUNTOS_FACTURA":
                                logger.info(
                                    "Correo de facturación sin adjuntos válidos (ID_CORREO=%s): %s",
                                    id_correo, id_mensaje,
                                )
                                self._alert_manager.correo_sin_adjuntos(
                                    email_uid=id_mensaje,
                                    motivo=obs_rechazo,
                                    correo_id=id_correo,
                                )
                                try:
                                    rechazo_handler = RechazoHandler()
                                    asyncio.run(rechazo_handler.manejar_sin_adjuntos(id_correo))
                                except Exception as e:
                                    logger.error(
                                        "Error al procesar rechazo sin adjuntos para ID_CORREO=%s: %s",
                                        id_correo, e,
                                    )
                            else:
                                logger.warning(
                                    "Correo rechazado por filtro (ID_CORREO=%s): %s | %s",
                                    id_correo, id_mensaje, motivo,
                                )
                                try:
                                    rechazo_handler = RechazoHandler()
                                    asyncio.run(rechazo_handler.procesar_rechazo(
                                        id_correo, obs_rechazo,
                                    ))
                                except Exception as e:
                                    logger.error(
                                        "Error al procesar notificación de rechazo para ID_CORREO=%s: %s",
                                        id_correo, e,
                                    )

                            conn.uid("store", uid, "+FLAGS", "\\Seen")
                            return True

                        # 5c. Descargar TODOS los adjuntos válidos
                        adjuntos = self._attachment_handler.descargar_todos_adjuntos(msg, parsed)
                        if not adjuntos:
                            motivo_fallo = "No se pudieron descargar los adjuntos del correo."
                            self._repository.crear_proceso_ingesta(
                                conn=conn_db,
                                id_proceso=IdTipoProceso.descarga_almacenamiento,
                                observacion=motivo_fallo,
                                id_estado=IdEstadoProceso.error,
                                correo_id=id_correo,
                                id_error=IdTipoError.fallo_descarga_adjuntos,
                            )
                            conn_db.commit()

                            self._alert_manager.adjunto_incompleto(
                                email_uid=id_mensaje, archivos=[],
                                motivo=motivo_fallo,
                            )
                            logger.error("Falla al descargar adjuntos para correo %s", id_mensaje)
                            try:
                                rechazo_handler = RechazoHandler()
                                asyncio.run(rechazo_handler.procesar_rechazo(
                                    id_correo, motivo_fallo,
                                ))
                            except Exception as e:
                                logger.error(
                                    "Error al registrar rechazo por fallo de descarga para ID_CORREO=%s: %s",
                                    id_correo, e,
                                )
                            conn.uid("store", uid, "+FLAGS", "\\Seen")
                            return False

                        # 5d. Clasificar adjuntos por tipo
                        zips = [a for a in adjuntos if a.extension == ".zip"]
                        xmls = [a for a in adjuntos if a.extension == ".xml"]
                        pdfs = [a for a in adjuntos if a.extension == ".pdf"]

                        todos_resultados = []

                        # 5e. Procesar ZIPs (si los hay)
                        if zips:
                            resultados_zip = self._procesar_zips(
                                zips=zips, conn_db=conn_db, id_correo=id_correo,
                                id_mensaje=id_mensaje, fecha_envio=fecha_envio, parsed=parsed,
                            )
                            todos_resultados.extend(resultados_zip)

                        # 5f. Procesar XMLs sueltos (con o sin PDFs correspondientes)
                        if xmls:
                            resultados_sueltos = self._procesar_sueltos(
                                xmls=xmls, pdfs=pdfs, conn_db=conn_db,
                                id_correo=id_correo, id_mensaje=id_mensaje,
                                fecha_envio=fecha_envio, parsed=parsed,
                            )
                            todos_resultados.extend(resultados_sueltos)

                        if not todos_resultados:
                            motivo_sin_pares = (
                                "Ningún par XML+PDF pudo procesarse exitosamente. "
                                "Los adjuntos no contenían archivos válidos de factura electrónica."
                            )
                            self._repository.crear_proceso_ingesta(
                                conn=conn_db,
                                id_proceso=IdTipoProceso.filtro_recepcion,
                                observacion=motivo_sin_pares[:255],
                                id_estado=IdEstadoProceso.error,
                                correo_id=id_correo,
                                id_error=IdTipoError.correo_sin_adjuntos_validos,
                            )
                            conn_db.commit()

                            logger.warning(
                                "Ningún par XML+PDF procesado exitosamente para correo %s",
                                id_mensaje,
                            )
                            try:
                                rechazo_handler = RechazoHandler()
                                asyncio.run(rechazo_handler.procesar_rechazo(
                                    id_correo, motivo_sin_pares,
                                ))
                            except Exception as e:
                                logger.error(
                                    "Error al registrar rechazo por procesamiento fallido para ID_CORREO=%s: %s",
                                    id_correo, e,
                                )
                            conn.uid("store", uid, "+FLAGS", "\\Seen")
                            return False

                        # 5g. Publicar eventos en cola
                        for res in todos_resultados:
                            if res.get("pdf_huerfano"):
                                evento = {
                                    "event_type": "pdf_huerfano_disponible",
                                    "id_mensaje_email": id_mensaje,
                                    "id_correo": id_correo,
                                    "id_adjunto_pdf": res["id_adjunto_pdf"],
                                    "parsed_subject": parsed,
                                    "ruta_pdf": res["ruta_pdf"],
                                    "remitente": remitente,
                                }
                            else:
                                evento = {
                                    "event_type": "factura_disponible",
                                    "id_mensaje_email": id_mensaje,
                                    "id_correo": id_correo,
                                    "id_adjunto_xml": res["id_adjunto_xml"],
                                    "id_adjunto_pdf": res["id_adjunto_pdf"],
                                    "parsed_subject": parsed,
                                    "ruta_xml": res["ruta_xml"],
                                    "ruta_pdf": res["ruta_pdf"],
                                    "remitente": remitente,
                                }
                            self._publisher.publish(evento, db_conn=conn_db)

                        conn_db.commit()
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        logger.debug(
                            "Correo procesado: %s | %d facturas encoladas",
                            id_mensaje, len(todos_resultados),
                        )
                        return True

                finally:
                    # Restaurar configuración anterior
                    self._attachment_handler = old_handler
                    self._validator.temp_root = old_temp_root

        except ConnectionError as ce:
            logger.error("Falla de infraestructura (reintentable) para correo UID=%s: %s", uid, ce)
            # Intentamos asegurar que el correo permanezca como no leído
            try:
                conn.uid("store", uid, "-FLAGS", "\\Seen")
            except Exception:
                pass
            return False
        except Exception as exc:
            logger.exception("Error fatal procesando correo UID=%s: %s", uid, exc)
            # En errores fatales desconocidos, marcamos como visto para evitar bucles infinitos de error
            # pero notificamos el fallo
            try:
                conn.uid("store", uid, "+FLAGS", "\\Seen")
            except Exception:
                pass
            return False

    def run(self):
        """Ejecuta un ciclo de ingesta."""
        try:
            with self._conectar() as conn:
                uids = self._obtener_uids(conn)
                if not uids:
                    logger.info("No hay correos nuevos para procesar")
                    return

                procesados = 0
                for uid in uids:
                    try:
                        if self._procesar_correo(conn, uid):
                            procesados += 1
                    except Exception as exc:
                        # Si es un error de conexión (infraestructura), abortamos todo el ciclo
                        # para no intentar procesar el resto de correos sin sentido.
                        if "Abortando procesamiento: ClamAV no disponible" in str(exc) or isinstance(exc, ConnectionError):
                            logger.critical("Abortando ciclo de ingesta: Infraestructura crítica no disponible.")
                            break
                        
                        logger.error("Error no crítico en correo UID=%s: %s", uid, exc)
                        continue

                logger.info("Ciclo completado: %d/%d procesados", procesados, len(uids))
        except Exception as exc:
            logger.error("Error en ciclo de ingesta: %s", exc)

    def run_forever(self):
        """Ejecuta el listener en bucle continuo."""
        logger.info("Iniciando listener continuo (poll_interval=%ds)", self.poll_interval)
        while True:
            try:
                self.run()
            except KeyboardInterrupt:
                logger.info("Listener detenido por usuario")
                break
            except Exception as exc:
                logger.exception("Error inesperado en ciclo principal: %s", exc)

            time.sleep(self.poll_interval)


if __name__ == "__main__":
    EmailListener().run_forever()
