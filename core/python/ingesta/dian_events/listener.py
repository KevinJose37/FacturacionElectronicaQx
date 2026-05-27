"""Listener IMAP especializado para eventos DIAN."""

import asyncio
import imaplib
import logging
import os
import random
import time
import email as _email
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from core.python.db.connection import get_pool, init_pool
from core.python.ingesta.dian_events.filter import DianEventFilter
from core.python.facturas.invoice_repository import InvoiceRepository
from config import load_yaml_queries
from utils.email_parser import EmailParser

load_dotenv()

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[4] / 'config' / 'settings.yaml'


def _load_config() -> dict:
    """Carga la configuración desde el archivo YAML."""
    with _CONFIG_PATH.open('r', encoding='utf-8') as fh:
        config = yaml.safe_load(fh)
    return config


_QUERIES = load_yaml_queries('eventos/queries_eventos.yml').get('eventos', {})


class DianEventListener:
    """Listener para el correo secundario que recibe solo eventos DIAN.

    Implementa polling IMAP con backoff exponencial + jitter para resiliencia
    ante caídas de red o del servidor de correo.
    """

    def __init__(self, config_path: str | None = None):
        """Inicializa el listener con configuración YAML y variables de entorno.

        Args:
            config_path:
                Ruta al archivo de configuración YAML. Si es None, usa la ruta por defecto.
        """
        if config_path:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = _load_config()

        # Configuración de conexión IMAP (reutiliza la sección `email` global)
        self.host = self.config['email']['host']
        self.port = int(self.config['email']['port'])
        self.user = os.environ.get('EMAIL_EVENTS_USER')
        self._password = os.environ.get('EMAIL_EVENTS_PASSWORD')
        self.folder = 'INBOX'

        if not self.user or not self._password:
            raise ValueError(
                'EMAIL_EVENTS_USER y EMAIL_EVENTS_PASSWORD deben estar definidos en el .env'
            )

        # Configuración del listener desde YAML (sin valores hardcodeados)
        listener_cfg = self.config.get('dian_events_listener', {})
        conn_cfg = listener_cfg.get('connection', {})

        self._poll_interval = int(listener_cfg.get('poll_interval_seconds', 30))
        self._max_backoff = int(listener_cfg.get('max_backoff_seconds', 300))
        self._jitter_max = int(listener_cfg.get('jitter_max_seconds', 5))
        self._max_conn_attempts = int(conn_cfg.get('max_attempts', 3))
        self._conn_backoff_base = float(conn_cfg.get('backoff_base_seconds', 2))

        self.filter = DianEventFilter()
        self.repo = InvoiceRepository()
        self.parser = EmailParser()

    # ------------------------------------------------------------------
    # Conexión IMAP con reintentos
    # ------------------------------------------------------------------

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Establece conexión IMAP con reintentos y backoff exponencial.

        Raises:
            ConnectionError: Si se agotan todos los intentos de conexión.
        """
        for intento in range(1, self._max_conn_attempts + 1):
            try:
                conn = imaplib.IMAP4_SSL(self.host, self.port)
                conn.login(self.user, self._password)
                conn.select(self.folder)
                return conn
            except (imaplib.IMAP4.error, OSError) as exc:
                if intento == self._max_conn_attempts:
                    raise ConnectionError(
                        f'Falla conexión IMAP tras {self._max_conn_attempts} intentos: {exc}'
                    )
                espera = self._conn_backoff_base ** intento
                logger.warning(
                    'Intento IMAP %d/%d fallido: %s — reintentando en %.1fs',
                    intento, self._max_conn_attempts, exc, espera,
                )
                time.sleep(espera)

    # ------------------------------------------------------------------
    # Procesamiento de correos individuales
    # ------------------------------------------------------------------

    def _decodificar_asunto(self, raw_subject: str) -> str:
        """Decodifica un asunto con posibles fragmentos MIME encoded.

        Args:
            raw_subject: Asunto crudo del header del correo.

        Returns:
            Asunto decodificado como texto plano.
        """
        decoded_parts = decode_header(raw_subject)
        subject = ''.join(
            str(part[0], part[1] or 'utf-8') if isinstance(part[0], bytes) else str(part[0])
            for part in decoded_parts
        )
        return subject

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
            if status != 'OK' or not data:
                logger.error('No se pudo obtener header del correo UID=%s', uid)
                return exito

            raw_header = data[0][1].decode(errors='ignore')
            msg = _email.message_from_string(raw_header)
            subject_raw = msg.get('Subject', '')
            sender = msg.get('From', '')
            date_raw = msg.get('Date', '')

            subject = self._decodificar_asunto(subject_raw)
            logger.info('Evaluando correo: %s | De: %s', subject, sender)

            fecha_envio = None
            if date_raw:
                try:
                    fecha_envio = parsedate_to_datetime(date_raw)
                except Exception as e:
                    logger.debug('No se pudo parsear fecha de envío: %s | error: %s', date_raw, e)

            res_filtro = self.filter.evaluate(sender, subject)

            if not res_filtro.is_dian_event:
                logger.info('Correo descartado: %s', res_filtro.reason)
                # Solo marcar como leído si realmente parece un correo de evento DIAN (empieza con "Evento")
                # pero fue descartado por remitente no autorizado, código inválido, etc.
                # Si no empieza con "Evento", lo dejamos sin leer (UNSEEN) para que el listener principal lo procese.
                if subject.strip().lower().startswith('evento'):
                    conn.uid('store', uid, '+FLAGS', '\\Seen')
                exito = True
            else:
                exito = await self._registrar_evento(conn, uid, subject, res_filtro, fecha_envio)

        except Exception as e:
            logger.exception('Error procesando correo UID %s: %s', uid, e)

        return exito

    async def _registrar_evento(self, conn, uid, subject, res_filtro, fecha_envio: datetime | None = None) -> bool:
        """Extrae el número de factura del asunto y persiste el evento DIAN.

        Args:
            conn: Conexión IMAP activa.
            uid: UID del correo.
            subject: Asunto decodificado.
            res_filtro: Resultado del filtro con event_code.
            fecha_envio: Fecha de envío original del correo electrónico.

        Returns:
            True si el evento fue registrado o el correo fue correctamente descartado.
        """
        parts = subject.split(';')
        num_factura = None

        if subject.lower().startswith('evento;') and len(parts) >= 2:
            num_factura = parts[1].strip()
        else:
            p_subj = self.parser.parsear(subject)
            num_factura = p_subj.get('num_factura') or (parts[2].strip() if len(parts) >= 3 else None)

        if not num_factura:
            logger.error('Sin factura en asunto: %s', subject)
            conn.uid('store', uid, '+FLAGS', '\\Seen')
            exito = False
            return exito

        pool = get_pool()
        async with pool.connection() as db_conn:
            async with db_conn.cursor() as cur:
                await cur.execute(_QUERIES['buscar_factura'], (num_factura, num_factura, num_factura))
                row = await cur.fetchone()

                if not row:
                    # Si no existe la factura en BD, verificamos la antigüedad del correo.
                    # Si tiene menos de 2 horas (7200 segundos), dejamos el correo como UNSEEN (sin leer)
                    # para permitir que el listener principal procese la factura primero.
                    # Si tiene más de 2 horas, asumimos que no se procesará y lo marcamos como leído.
                    es_nuevo = True
                    if fecha_envio:
                        if fecha_envio.tzinfo is None:
                            fecha_envio = fecha_envio.replace(tzinfo=timezone.utc)
                        diff = datetime.now(timezone.utc) - fecha_envio.astimezone(timezone.utc)
                        if diff.total_seconds() > 7200:
                            es_nuevo = False
                    
                    if es_nuevo:
                        logger.warning('Factura [%s] no encontrada en BD. Se deja UNSEEN para reintento.', num_factura)
                    else:
                        logger.warning('Factura [%s] no encontrada en BD tras 2 horas. Se marca como LEÍDO (\\\\Seen) para descartar.', num_factura)
                        conn.uid('store', uid, '+FLAGS', '\\Seen')
                    
                    exito = True
                    return exito

                id_fac = row[0]
                cod_ev = res_filtro.event_code

                # 1. Registrar SIEMPRE el evento en la tabla de trazabilidad
                await cur.execute(_QUERIES['insertar_evento'], (id_fac, cod_ev, f'Evento email: {subject}'))

                # 2. Actualizar checks en factura_control SOLO si es un código de control (030, 032, 033)
                from metadata.eventos_dian_metadata import EventosDianMetadata
                if cod_ev in EventosDianMetadata.codigos_control:
                    await cur.execute(_QUERIES['actualizar_control'], (cod_ev, cod_ev, cod_ev, id_fac))
                    logger.info('Checks de factura_control actualizados para evento %s', cod_ev)

                await db_conn.commit()
                logger.info('Evento %s procesado exitosamente para factura %s', cod_ev, id_fac)
                conn.uid('store', uid, '+FLAGS', '\\Seen')
                exito = True

        return exito

    # ------------------------------------------------------------------
    # Ciclo de polling
    # ------------------------------------------------------------------

    async def run_once(self) -> bool:
        """Ejecuta un ciclo de búsqueda y procesamiento.

        Returns:
            True si el ciclo fue exitoso (sin excepciones), False en caso contrario.
        """
        conn = None
        try:
            conn = self._connect()
            status, data = conn.uid('search', None, 'UNSEEN SUBJECT "Evento"')
            if status == 'OK':
                uids = data[0].split()
                for uid in uids:
                    await self._process_email(conn, uid)
            exito = True
        except ConnectionError as ce:
            logger.error('Fallo de conexión IMAP: %s', ce)
            exito = False
        except Exception as e:
            logger.error('Error en ciclo de eventos DIAN: %s', e)
            exito = False
        finally:
            if conn:
                try:
                    conn.logout()
                except Exception:
                    pass

        return exito

    def _calcular_espera(self, fallos_consecutivos: int) -> float:
        """Calcula el tiempo de espera con backoff exponencial + jitter.

        Fórmula: min(max_backoff, base * 2^(fallos-1)) + random(0, jitter_max).
        El jitter previene el efecto thundering herd cuando múltiples instancias
        reintentan simultáneamente tras una caída compartida.

        Args:
            fallos_consecutivos: Cantidad de fallos consecutivos acumulados.

        Returns:
            Tiempo de espera en segundos.
        """
        if fallos_consecutivos == 0:
            base = self._poll_interval
        else:
            base = min(
                self._max_backoff,
                self._poll_interval * (2 ** (fallos_consecutivos - 1)),
            )
        jitter = random.uniform(0, self._jitter_max)
        espera = base + jitter
        return espera

    async def run_forever(self) -> None:
        """Mantiene el listener en ejecución continua con backoff exponencial + jitter."""
        logger.info('Iniciando Listener de Eventos DIAN en %s...', self.user)
        await init_pool()

        fallos_consecutivos = 0

        try:
            while True:
                exito = await self.run_once()

                if exito:
                    fallos_consecutivos = 0
                else:
                    fallos_consecutivos += 1

                tiempo_espera = self._calcular_espera(fallos_consecutivos)

                if fallos_consecutivos > 0:
                    logger.warning(
                        'Fallo consecutivo #%d. Esperando %.1fs antes de reintentar...',
                        fallos_consecutivos, tiempo_espera,
                    )

                await asyncio.sleep(tiempo_espera)
        finally:
            from core.python.db.connection import close_pool
            await close_pool()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    )

    listener = DianEventListener()
    asyncio.run(listener.run_forever())
