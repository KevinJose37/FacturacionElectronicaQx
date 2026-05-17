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

    async def _process_email(self, conn: imaplib.IMAP4_SSL, uid: bytes) -> bool:
        """Procesa un correo individual buscando eventos DIAN.

        Args:
            conn: Conexión IMAP activa.
            uid: Identificador único del correo.

        Returns:
            Verdadero si el proceso fue exitoso o el correo fue descartado.
        """
        exito = False
        try:
            status, data = conn.uid('fetch', uid, '(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])')
            if status == 'OK' and data:
                raw_header = data[0][1].decode(errors='ignore')
                msg = _email.message_from_string(raw_header)
                subject_raw = msg.get('Subject', '')
                sender = msg.get('From', '')
                from email.header import decode_header
                decoded = decode_header(subject_raw)
                subject = ''.join(str(p[0], p[1] or 'utf-8') if isinstance(p[0], bytes) else str(p[0]) for p in decoded)
                logger.info(f'Evaluando correo: {subject} | De: {sender}')
                res_filtro = self.filter.evaluate(sender, subject)
                if not res_filtro.is_dian_event:
                    logger.info(f'Correo descartado: {res_filtro.reason}')
                    conn.uid('store', uid, '+FLAGS', '\\Seen')
                    exito = True
                else:
                    parts = subject.split(';')
                    num_factura = None
                    if subject.lower().startswith('evento;') and len(parts) >= 2:
                        num_factura = parts[1].strip()
                    else:
                        p_subj = self.parser.parsear(subject)
                        num_factura = p_subj.get('num_factura') or (parts[2].strip() if len(parts) >= 3 else None)

                    if not num_factura:
                        logger.error(f'Sin factura en asunto: {subject}')
                        conn.uid('store', uid, '+FLAGS', '\\Seen')
                    else:
                        pool = get_pool()
                        async with pool.connection() as db_conn:
                            async with db_conn.cursor() as cur:
                                query = "SELECT id_factura FROM facturacion.factura WHERE numero_factura = %s OR prefijo_facturacion || '-' || numero_factura = %s OR prefijo_facturacion || numero_factura = %s LIMIT 1"
                                await cur.execute(query, (num_factura, num_factura, num_factura))
                                row = await cur.fetchone()
                                if not row:
                                    logger.warning(f'Factura [{num_factura}] no encontrada.')
                                    conn.uid('store', uid, '+FLAGS', '\\Seen')
                                    exito = True
                                else:
                                    id_fac = row[0]
                                    
                                    # 1. Registrar el evento en la tabla de trazabilidad
                                    ins_ev = "INSERT INTO facturacion.evento_dian_factura (id_factura, codigo_evento, descripcion, fecha_evento) VALUES (%s, %s, %s, NOW())"
                                    await cur.execute(ins_ev, (id_fac, res_filtro.event_code, f'Evento email: {subject}'))
                                    
                                    # 2. Actualizar directamente el check correspondiente en factura_control
                                    # Solo para facturas que NO sean de CONTADO (codigo_forma_pago != '1')
                                    update_sql = """
                                        UPDATE facturacion.factura_control fc
                                        SET 
                                            acuso_recibido = CASE WHEN %s = '030' THEN TRUE ELSE acuso_recibido END,
                                            recibido_bien_servicio = CASE WHEN %s = '032' THEN TRUE ELSE recibido_bien_servicio END,
                                            aceptacion_expresa = CASE WHEN %s = '033' THEN TRUE ELSE aceptacion_expresa END,
                                            fecha_actualizacion = NOW()
                                        FROM facturacion.pago_factura pf
                                        WHERE fc.id_factura = %s 
                                          AND fc.id_factura = pf.id_factura
                                          AND pf.codigo_forma_pago != '1'
                                    """
                                    await cur.execute(update_sql, (res_filtro.event_code, res_filtro.event_code, res_filtro.event_code, id_fac))
                                    
                                    await db_conn.commit()
                                    logger.info(f'Evento {res_filtro.event_code} procesado y checks actualizados para factura {id_fac}')
                                    conn.uid('store', uid, '+FLAGS', '\\Seen')
                                    exito = True
        except Exception as e:
            logger.exception(f'Error procesando correo UID {uid}: {e}')
        return exito

    async def run_once(self) -> None:
        """Ejecuta un ciclo de búsqueda y procesamiento."""
        try:
            conn = self._connect()
            status, data = conn.uid('search', None, 'UNSEEN')
            if status == 'OK':
                uids = data[0].split()
                for uid in uids:
                    await self._process_email(conn, uid)
            conn.logout()
        except Exception as e:
            logger.error(f'Error en ciclo de eventos DIAN: {e}')

    async def run_forever(self) -> None:
        """Mantiene el listener en ejecución continua."""
        logger.info(f'Iniciando Listener de Eventos DIAN en {self.user}...')
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
