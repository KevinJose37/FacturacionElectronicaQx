"""Listener de correos IMAP para ingesta de facturas electrónicas."""

from __future__ import annotations

import imaplib
import logging
import os
import time
import email as _email
from datetime import datetime, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime

import yaml
from dotenv import load_dotenv

from config import get_postgres_config
from core.python.ingesta.queue_publisher import get_publisher

from metadata.db_metadata import IdEstadoProceso
from metadata.db_metadata import IdTipoArchivo

from utils.alerts import AlertManager
from utils.attachment_handler import AttachmentHandler
from utils.attachment_validator import AttachmentValidator
from utils.email_parser import EmailParser
from utils.email_repository import EmailRepository
from utils.factura_filter import FacturaFilter
from utils.malware_scanner import MalwareScanner

load_dotenv()

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "settings.yaml"


def _load_config() -> dict:
    """Carga la configuración desde el archivo YAML."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuración no encontrada en {_CONFIG_PATH}")
    with _CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


_CONFIG = _load_config()
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

    def _obtener_uids(self, conn: imaplib.IMAP4_SSL) -> list[bytes]:
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

    def _procesar_correo(self, conn: imaplib.IMAP4_SSL, uid: bytes) -> bool:
        """Procesa un correo individual con flujo completo."""
        try:
            # 1. FETCH del correo
            status, data = conn.uid("fetch", uid, "(RFC822)")
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

            if fecha_envio_raw:
                try:
                    fecha_envio = parsedate_to_datetime(fecha_envio_raw)

                except Exception as e:
                    logger.debug("No se pudo parsear fecha de envío: %s | error: %s", fecha_envio_raw, e)
                    fecha_envio = None

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

            # 4. Verificar si tiene adjunto ZIP
            tiene_zip = self._attachment_handler._tiene_adjunto_zip(raw)

            # 5. Procesamiento principal con transacción
            with self._repository._get_connection() as conn_db:
                try:
                    # 5a. Guardar correo en BD (registro histórico)
                    id_correo = self._repository.guardar_correo_entrante(
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
                    if not id_correo:
                        logger.warning("Correo ya existente en BD: %s. Marcando como leído.", id_mensaje)
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        return True

                    # 5b. Aplicar filtro de facturación (para flujo de ingesta completo)
                    resultado_filtro = filtro.evaluar(parsed, tiene_zip, remitente)

                    if not resultado_filtro.es_factura:
                        if resultado_filtro.motivo_rechazo == "SIN_ADJUNTO_ZIP":
                            logger.info("Correo de facturación registrado sin ZIP (ID_CORREO=%s): %s", id_correo, id_mensaje)
                            self._alert_manager.adjunto_incompleto(
                                email_uid=id_mensaje,
                                archivos=[],
                                motivo="El correo de facturación no contiene un archivo ZIP adjunto"
                            )
                            conn.uid("store", uid, "+FLAGS", "\\Seen")
                            return True  # Registro exitoso, pero sin ingesta

                        self._alert_manager.factura_rechazada(
                            motivo=resultado_filtro.motivo_rechazo or "No cumple criterios de factura",
                            nit=parsed.get("nit"),
                            num_factura=parsed.get("num_factura"),
                        )
                        logger.warning("Correo de facturación rechazado por filtro: %s | Motivo: %s", id_mensaje, resultado_filtro.motivo_rechazo)
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        return True # Registrado en CORREO_ENTRANTE, pero marcado como rechazado en flujo

                    # 5c. Descargar ZIP
                    ruta_zip = self._attachment_handler.descargar_zip(msg, parsed)
                    if not ruta_zip:
                        self._alert_manager.adjunto_incompleto(
                            email_uid=id_mensaje,
                            archivos=[],
                            motivo="No se pudo descargar ZIP",
                        )
                        logger.error("Falla al descargar ZIP para correo %s", id_mensaje)
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        return False

                    # 5c.1 Verificar si el ZIP ya fue procesado antes (hash repetido)
                    sha256_zip = self._repository.calcular_hash_sha256(ruta_zip)
                    if self._repository.existe_adjunto_por_hash(conn_db, sha256_zip):
                        logger.warning("El archivo ZIP ya existe en la tabla adjuntos_correo (Hash: %s). Se omitirá su procesamiento.", sha256_zip[:8])
                        try:
                            ruta_zip.unlink(missing_ok=True)
                        except Exception:
                            pass
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        return True

                    # 5d. Validar contenido del ZIP (XML + PDF)
                    validacion = self._validator.validar_zip(ruta_zip)
                    if not validacion.es_valido:
                        try:
                            ruta_zip.unlink(missing_ok=True)
                        except Exception:
                            pass
                        self._alert_manager.adjunto_incompleto(
                            email_uid=id_mensaje,
                            archivos=validacion.archivos_encontrados,
                            motivo=validacion.motivo_error or "Validación fallida",
                        )
                        logger.error("Validación de adjuntos falló: %s | %s", id_mensaje, validacion.motivo_error)
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        return False

                    # 5e. Escaneo de malware sobre ZIP, XML y PDF
                    scan_zip = self._scanner.escanear_archivo(ruta_zip)
                    if not scan_zip.seguro:
                        try:
                            ruta_zip.unlink(missing_ok=True)
                        except Exception:
                            pass
                        self._alert_manager.malware_detectado(ruta_zip.name, scan_zip.nivel_riesgo)
                        logger.critical("Malware detectado en ZIP: %s | %s", ruta_zip, scan_zip.detalle)
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        return False

                    scan_xml = self._scanner.escanear_archivo(validacion.xml_path)
                    if not scan_xml.seguro:
                        try:
                            ruta_zip.unlink(missing_ok=True)
                        except Exception:
                            pass
                        self._alert_manager.malware_detectado(validacion.xml_path.name, scan_xml.nivel_riesgo)
                        logger.critical("Malware detectado en XML: %s | %s", validacion.xml_path, scan_xml.detalle)
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        return False

                    scan_pdf = self._scanner.escanear_archivo(validacion.pdf_path)
                    if not scan_pdf.seguro:
                        try:
                            ruta_zip.unlink(missing_ok=True)
                        except Exception:
                            pass
                        self._alert_manager.malware_detectado(validacion.pdf_path.name, scan_pdf.nivel_riesgo)
                        logger.critical("Malware detectado en PDF: %s | %s", validacion.pdf_path, scan_pdf.detalle)
                        conn.uid("store", uid, "+FLAGS", "\\Seen")
                        return False

                    # 5f. Guardar adjuntos en BD con jerarquía (ZIP -> XML/PDF)
                    # El ZIP es el padre
                    id_adjunto_zip = self._repository.guardar_adjunto_correo(
                        conn=conn_db,
                        id_correo=id_correo,
                        ruta_archivo=ruta_zip,
                        id_tipo_archivo=IdTipoArchivo.zip,
                        archivo_seguro=scan_zip.seguro,
                        fecha_envio=fecha_envio
                    )

                    # Mover XML y PDF desde temp a ubicación permanente y guardarlos como hijos del ZIP
                    xml_destino = self._attachment_handler.construir_ruta_destino(validacion.xml_path.name, parsed)
                    pdf_destino = self._attachment_handler.construir_ruta_destino(validacion.pdf_path.name, parsed)
                    xml_destino.parent.mkdir(parents=True, exist_ok=True)
                    pdf_destino.parent.mkdir(parents=True, exist_ok=True)
                    validacion.xml_path.replace(xml_destino)
                    validacion.pdf_path.replace(pdf_destino)

                    id_adjunto_xml = self._repository.guardar_adjunto_correo(
                        conn=conn_db,
                        id_correo=id_correo,
                        ruta_archivo=xml_destino,
                        id_tipo_archivo=IdTipoArchivo.xml,
                        adjunto_padre_id=id_adjunto_zip,
                        archivo_seguro=scan_xml.seguro,
                        fecha_envio=fecha_envio
                    )

                    id_adjunto_pdf = self._repository.guardar_adjunto_correo(
                        conn=conn_db,
                        id_correo=id_correo,
                        ruta_archivo=pdf_destino,
                        id_tipo_archivo=IdTipoArchivo.pdf,
                        adjunto_padre_id=id_adjunto_zip,
                        archivo_seguro=scan_pdf.seguro,
                        fecha_envio=fecha_envio
                    )

                    # 5h. Crear proceso de ingesta
                    id_proceso = self._repository.crear_proceso_ingesta(
                        conn=conn_db,
                        id_correo=id_correo,
                        id_adjunto=id_adjunto_zip,
                    )

                    # 5j. Publicar evento en cola (con datos completos)
                    evento = {
                        "event_type": "factura_disponible",
                        "id_mensaje_email": id_mensaje,
                        "id_correo": id_correo,
                        "id_proceso": id_proceso,
                        "id_adjunto_zip": id_adjunto_zip,
                        "id_adjunto_xml": id_adjunto_xml,
                        "id_adjunto_pdf": id_adjunto_pdf,
                        "parsed_subject": parsed,
                        "ruta_zip": str(ruta_zip),
                        "ruta_xml": str(xml_destino),
                        "ruta_pdf": str(pdf_destino),
                        "remitente": remitente,
                    }
                    if not self._publisher.publish(evento, db_conn=conn_db):
                        raise RuntimeError("No se pudo publicar evento en cola")

                    # Si llegamos aquí, todo OK; el with conn_db hará commit automáticamente
                    conn.uid("store", uid, "+FLAGS", "\\Seen")
                    logger.info("Factura procesada y encolada: %s | ID_proceso=%s", id_mensaje, id_proceso)
                    return True

                finally:
                    # Limpiar archivos temporales (si quedan)
                    try:
                        self._validator.limpiar_temp()
                    except Exception as e:
                        logger.warning("Error limpiando temp: %s", e)

        except Exception as exc:
            logger.exception("Error procesando correo UID=%s: %s", uid, exc)
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
                    if self._procesar_correo(conn, uid):
                        procesados += 1

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
