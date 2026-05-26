"""Worker de colas de trabajo para procesar facturas asíncronamente."""

import logging
import os
import select
import signal
import socket
import time
from typing import List, Dict, Any

from config import get_postgres_config
from core.python.db.connection import get_pool
from core.python.facturas.invoice_processor import InvoiceProcessor
from core.python.ingesta.queue_config import QueueWorkerConfig
from metadata.db_metadata import IdEstadoProceso

logger = logging.getLogger(__name__)


class QueueWorker:
    """Worker que consume la tabla EVENTO_INGESTA usando FOR UPDATE SKIP LOCKED."""

    def __init__(self):
        """Inicializa el worker con su ID y configuración."""
        self.worker_id = f"{socket.gethostname()}-{os.getpid()}"
        self.running = False
        self.processor = InvoiceProcessor()
        
        # Conexión independiente para el worker
        import psycopg
        db_config = get_postgres_config()
        self.conninfo = f"host={db_config['host']} port={db_config['port']} dbname={db_config['dbname']} user={db_config['user']} password={db_config['password']}"

    def claim_jobs(self, conn) -> List[Dict[str, Any]]:
        """Reclama jobs pendientes atómicamente."""
        query = """
        WITH batch AS (
            SELECT ADJUNTO_ID
            FROM FACTURACION.EVENTO_INGESTA
            WHERE ID_ESTADO = %(estado_pendiente)s
              AND INTENTOS < %(max_intentos)s
              AND FECHA_ACTUALIZACION <= NOW()
            ORDER BY FECHA_CREACION ASC
            FOR UPDATE SKIP LOCKED
            LIMIT %(batch_size)s
        ),
        updated AS (
            UPDATE FACTURACION.EVENTO_INGESTA ei
            SET ID_ESTADO = %(estado_en_proceso)s,
                WORKER_ID = %(worker_id)s,
                FECHA_ACTUALIZACION = NOW()
            FROM batch
            WHERE ei.ADJUNTO_ID = batch.ADJUNTO_ID
            RETURNING ei.*
        )
        SELECT u.*, a.NOMBRE_ARCHIVO, a.ID_TIPO_ARCHIVO, a.URI_ALMACENAMIENTO, a.ADJUNTO_PADRE_ID, a.SHA256,
               (
                   WITH RECURSIVE adj_tree AS (
                       SELECT ac1.ADJUNTO_ID as raiz, ac1.ADJUNTO_ID, ac1.ADJUNTO_PADRE_ID
                       FROM FACTURACION.ADJUNTOS_CORREO ac1
                       WHERE ac1.ADJUNTO_ID = u.ADJUNTO_ID AND ac1.ADJUNTO_PADRE_ID IS NULL
                       UNION ALL
                       SELECT t.raiz, ac2.ADJUNTO_ID, ac2.ADJUNTO_PADRE_ID
                       FROM FACTURACION.ADJUNTOS_CORREO ac2
                       JOIN adj_tree t ON ac2.ADJUNTO_ID = t.ADJUNTO_PADRE_ID
                   )
                   SELECT raiz FROM adj_tree WHERE ADJUNTO_PADRE_ID IS NULL LIMIT 1
               ) as adjunto_raiz_id
        FROM updated u
        JOIN FACTURACION.ADJUNTOS_CORREO a ON a.ADJUNTO_ID = u.ADJUNTO_ID;
        """
        
        with conn.cursor() as cur:
            cur.execute(query, {
                'estado_pendiente': IdEstadoProceso.pendiente,
                'max_intentos': QueueWorkerConfig.max_reintentos,
                'batch_size': QueueWorkerConfig.batch_size,
                'estado_en_proceso': IdEstadoProceso.en_proceso,
                'worker_id': self.worker_id,
            })
            
            rows = cur.fetchall()
            if not rows:
                return []
                
            cols = [desc[0] for desc in cur.description]
            jobs = [dict(zip(cols, row)) for row in rows]
            return jobs

    # Cooldown en segundos para jobs que retornan retry_later (ej: PDF huérfano
    # esperando que su factura sea procesada).  Evita bucles tight de reintentos.
    RETRY_LATER_COOLDOWN_SECONDS = 4

    def handle_failed_job(self, conn, adjunto_id: int):
        """Marca un job como fallido (incrementa intentos o lo pone en error)."""
        query = """
        UPDATE FACTURACION.EVENTO_INGESTA
        SET INTENTOS = INTENTOS + 1,
            ID_ESTADO = CASE 
                WHEN INTENTOS + 1 >= %(max_intentos)s THEN %(estado_fallido)s
                ELSE %(estado_pendiente)s 
            END,
            WORKER_ID = NULL,
            FECHA_ACTUALIZACION = NOW()
        WHERE ADJUNTO_ID = %(adjunto_id)s;
        """
        with conn.cursor() as cur:
            cur.execute(query, {
                'max_intentos': QueueWorkerConfig.max_reintentos,
                'estado_fallido': IdEstadoProceso.fallido,
                'estado_pendiente': IdEstadoProceso.pendiente,
                'adjunto_id': adjunto_id,
            })

    def handle_retry_later(self, conn, adjunto_id: int):
        """Pone un job en cooldown sin incrementar intentos.

        Actualiza FECHA_ACTUALIZACION al futuro para que claim_jobs
        no lo reclame durante el periodo de cooldown.  El estado
        vuelve a PENDIENTE y WORKER_ID se libera.
        """
        query = f"""
        UPDATE FACTURACION.EVENTO_INGESTA
        SET ID_ESTADO = %(estado_pendiente)s,
            WORKER_ID = NULL,
            FECHA_ACTUALIZACION = NOW() + INTERVAL '{self.RETRY_LATER_COOLDOWN_SECONDS} seconds'
        WHERE ADJUNTO_ID = %(adjunto_id)s;
        """
        with conn.cursor() as cur:
            cur.execute(query, {
                'estado_pendiente': IdEstadoProceso.pendiente,
                'adjunto_id': adjunto_id,
            })
        logger.info(
            'Job adjunto_id=%s en cooldown por %d segundos (retry_later).',
            adjunto_id, self.RETRY_LATER_COOLDOWN_SECONDS,
        )

    def recover_stuck_jobs(self, conn):
        """Resetea jobs que quedaron atascados en EN_PROCESO."""
        query = f"""
        UPDATE FACTURACION.EVENTO_INGESTA
        SET ID_ESTADO = %(estado_pendiente)s,
            WORKER_ID = NULL,
            FECHA_ACTUALIZACION = NOW()
        WHERE ID_ESTADO = %(estado_en_proceso)s
          AND FECHA_ACTUALIZACION < NOW() - INTERVAL '{QueueWorkerConfig.stuck_job_timeout_minutes} minutes';
        """
        
        with conn.cursor() as cur:
            cur.execute(query, {
                'estado_pendiente': IdEstadoProceso.pendiente,
                'estado_en_proceso': IdEstadoProceso.en_proceso,
            })
            stuck_count = cur.rowcount
            if stuck_count > 0:
                logger.warning('Recuperados %d jobs atascados', stuck_count)
            conn.commit()

    def stop(self, signum, frame):
        """Detiene el loop principal."""
        logger.info('Señal de parada recibida (%s). Deteniendo worker %s...', signum, self.worker_id)
        self.running = False

    def run(self):
        """Loop principal del worker."""
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        
        self.running = True
        logger.info('Iniciando QueueWorker %s', self.worker_id)
        
        import psycopg
        
        while self.running:
            try:
                with psycopg.connect(self.conninfo) as conn:
                    # Recuperar jobs atascados al iniciar/reconectar
                    self.recover_stuck_jobs(conn)
                    
                    while self.running:
                        # 1. Reclamar jobs
                        conn.execute("BEGIN;")
                        jobs = self.claim_jobs(conn)
                        conn.commit()
                        
                        if not jobs:
                            # 2. Esperar nuevos jobs de forma bloqueante ligera
                            # LISTEN/NOTIFY es el trigger primario, sleep es el fail-safe
                            conn.execute("LISTEN factura_nueva;")
                            conn.commit()
                            
                            # Esperar notificación o timeout usando select (fail-safe cada 10 segs)
                            # Esto es eficiente y no consume CPU
                            if select.select([conn.pgconn.socket], [], [], 10.0) == ([], [], []):
                                logger.debug("Timeout de espera de notificación (10s).")
                            else:
                                # Hay actividad en el socket, procesar notificaciones
                                # Esto hace que psycopg lea las notificaciones del buffer
                                conn.pgconn.consume_input()
                                logger.debug("Notificación de DB recibida.")
                            
                            conn.execute("UNLISTEN factura_nueva;")
                            conn.commit()
                            continue
                            
                        logger.info('Worker %s procesando %d jobs', self.worker_id, len(jobs))
                        
                        # 3. Agrupar en familias y procesar
                        # Simulamos lo que hace procesar_pendientes
                        familias = self.processor._agrupar_por_familia(jobs)
                        
                        for familia_id, familia in familias.items():
                            if not self.running:
                                break
                            
                            try:
                                # Delegate real logic to InvoiceProcessor
                                # We need a new connection since InvoiceProcessor creates its own or uses the pool
                                result = self.processor._procesar_familia(familia)
                                if result == 'fail':
                                    logger.error('Fallo procesando familia %s', familia_id)
                                    conn.execute("BEGIN;")
                                    for job in familia:
                                        self.handle_failed_job(conn, job['adjunto_id'])
                                    conn.commit()
                                elif result == 'retry_later':
                                    # Cooldown: no incrementar intentos, solo postergar
                                    conn.execute("BEGIN;")
                                    for job in familia:
                                        self.handle_retry_later(conn, job['adjunto_id'])
                                    conn.commit()
                            except Exception as e:
                                logger.exception('Error inesperado procesando familia %s: %s', familia_id, e)
                                conn.execute("BEGIN;")
                                for job in familia:
                                    self.handle_failed_job(conn, job['adjunto_id'])
                                conn.commit()
                                
            except psycopg.OperationalError as e:
                logger.error('Error de conexión a PostgreSQL: %s', e)
                if self.running:
                    time.sleep(QueueWorkerConfig.poll_interval_seconds)
            except Exception as e:
                logger.exception('Error crítico en el worker: %s', e)
                if self.running:
                    time.sleep(QueueWorkerConfig.poll_interval_seconds)

        logger.info('QueueWorker %s detenido correctamente', self.worker_id)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    worker = QueueWorker()
    worker.run()
