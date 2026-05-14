"""Listener IMAP especializado para eventos DIAN."""

import imaplib
import logging
import os
import time
import email as _email
from datetime import datetime, timezone
from pathlib import Path
import yaml
from dotenv import load_dotenv

from core.python.db.connection import get_pool, init_pool
from core.python.ingesta.dian_events.filter import DianEventFilter
from core.python.facturas.invoice_repository import InvoiceRepository
from utils.email_parser import EmailParser

load_dotenv()

logger = logging.getLogger(__name__)

class DianEventListener:
    """Listener para el correo secundario que recibe solo eventos DIAN."""

    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        self.host = self.config["email"]["host"]
        self.port = int(self.config["email"]["port"])
        self.user = os.environ.get("EMAIL_EVENTS_USER")
        self._password = os.environ.get("EMAIL_EVENTS_PASSWORD")
        self.folder = "INBOX"
        
        if not self.user or not self._password:
            raise ValueError("EMAIL_EVENTS_USER y EMAIL_EVENTS_PASSWORD deben estar definidos en el .env")
            
        self.filter = DianEventFilter()
        self.repo = InvoiceRepository()
        self.parser = EmailParser()

    def _connect(self):
        conn = imaplib.IMAP4_SSL(self.host, self.port)
        conn.login(self.user, self._password)
        conn.select(self.folder)
        return conn

    async def _process_email(self, conn, uid):
        try:
            status, data = conn.uid("fetch", uid, "(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])")
            if status != "OK": return False
            
            raw_header = data[0][1].decode(errors='ignore')
            msg = _email.message_from_string(raw_header)
            
            subject = msg.get("Subject", "")
            sender = msg.get("From", "")
            
            # Decodificar asunto si viene en MIME encoding
            from email.header import decode_header
            decoded_parts = decode_header(subject)
            subject = "".join(
                str(p[0], p[1] or 'utf-8') if isinstance(p[0], bytes) else str(p[0])
                for p in decoded_parts
            )
            
            logger.info(f"Evaluando correo de eventos: {subject}")
            
            result = self.filter.evaluate(sender, subject)
            if not result.is_dian_event:
                logger.debug(f"Correo ignorado: {result.reason}")
                conn.uid("store", uid, "+FLAGS", "\\Seen")
                return True

            # Es un evento válido (030, 032, 033)
            parsed = self.parser.parsear(subject)
            num_factura = parsed.get("num_factura")
            
            if not num_factura:
                parts = subject.split(";")
                if len(parts) >= 3:
                    num_factura = parts[2].strip()

            if not num_factura:
                logger.error(f"No se pudo extraer número de factura del asunto: {subject}")
                conn.uid("store", uid, "+FLAGS", "\\Seen")
                return False

            # 2. Buscar la factura en la BD para obtener su ID
            pool = get_pool()
            async with pool.connection() as db_conn:
                async with db_conn.cursor() as cur:
                    await cur.execute(
                        "SELECT id_factura FROM facturacion.factura WHERE numero_factura = %s OR prefijo_facturacion || '-' || numero_factura = %s LIMIT 1",
                        (num_factura, num_factura)
                    )
                    res = await cur.fetchone()
                    if not res:
                        logger.warning(f"Factura {num_factura} no encontrada en BD. No se puede registrar evento {result.event_code}")
                        return False
                    
                    id_factura = res[0]
                    
                    await cur.execute(
                        """
                        INSERT INTO facturacion.evento_dian_factura (id_factura, codigo_evento, descripcion, fecha_evento)
                        VALUES (%s, %s, %s, NOW())
                        """,
                        (id_factura, result.event_code, f"Evento recibido vía email CEN: {subject}")
                    )
                    await db_conn.commit()
                    logger.info(f"Evento {result.event_code} registrado para factura ID {id_factura} (Num: {num_factura})")
                    
            conn.uid("store", uid, "+FLAGS", "\\Seen")
            return True

        except Exception as e:
            logger.exception(f"Error procesando correo de evento UID {uid}: {e}")
            return False

    async def run_once(self):
        try:
            conn = self._connect()
            status, data = conn.uid("search", None, "UNSEEN")
            if status == "OK":
                uids = data[0].split()
                for uid in uids:
                    await self._process_email(conn, uid)
            conn.logout()
        except Exception as e:
            logger.error(f"Error en ciclo de eventos DIAN: {e}")

    async def run_forever(self):
        logger.info(f"Iniciando Listener de Eventos DIAN en {self.user}...")
        await init_pool()
        try:
            while True:
                await self.run_once()
                await asyncio.sleep(30)
        finally:
            from core.python.db.connection import close_pool
            await close_pool()

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    config_p = str(Path(__file__).resolve().parents[4] / "config" / "settings.yaml")
    
    listener = DianEventListener(config_p)
    asyncio.run(listener.run_forever())
