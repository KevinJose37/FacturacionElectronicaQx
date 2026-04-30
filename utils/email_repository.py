"""Repositorio para persistencia de correos y adjuntos en PostgreSQL.

Gestiona la inserción de:
    - Correos entrantes (CORREO_ENTRANTE)
    - Archivos adjuntos (ARCHIVO y ADJUNTO_CORREO)
    - Relaciones entre ellos
    - Procesos de ingesta y logs

Garantiza idempotencia mediante únicos (ID_MENSAJE_EMAIL, HASH_SHA256).
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

import psycopg
from psycopg import Connection
from config import get_postgres_config

logger = logging.getLogger(__name__)


class EmailRepository:
    """Repositorio para operaciones de persistencia de correos."""

    def __init__(self, config: Optional[dict] = None):
        """Inicializa el repositorio.

        Args:
            config: Configuración de BD (si None, se lee de entorno).
        """
        self.config = config or get_postgres_config()

    def _get_connection(self) -> Connection:
        """Crea una nueva conexión a la BD."""
        return psycopg.connect(
            host=self.config["host"],
            port=int(self.config["port"]),
            dbname=self.config["dbname"],
            user=self.config["user"],
            password=self.config["password"],
        )

    def _calcular_hash_sha256(self, ruta_archivo: Path) -> str:
        """Calcula el SHA256 de un archivo."""
        sha256 = hashlib.sha256()
        with ruta_archivo.open("rb") as f:
            for bloque in iter(lambda: f.read(65536), b""):
                sha256.update(bloque)
        return sha256.hexdigest()

    def _detectar_mime_type(self, ruta_archivo: Path) -> str:
        """Detecta el tipo MIME de un archivo."""
        mime, _ = mimetypes.guess_type(str(ruta_archivo))
        return mime or "application/octet-stream"

    def guardar_archivo(
        self, conn: Connection, ruta: Path, nombre_original: Optional[str] = None
    ) -> Optional[int]:
        """Guarda un archivo en la tabla ARCHIVO (sin commit)."""
        if not ruta.exists():
            logger.error("Archivo no existe: %s", ruta)
            raise FileNotFoundError(f"Archivo no encontrado: {ruta}")

        hash_sha256 = self._calcular_hash_sha256(ruta)
        tamano = ruta.stat().st_size
        mime_type = self._detectar_mime_type(ruta)
        nombre = nombre_original or ruta.name
        fecha_creacion = datetime.now(tz=timezone.utc)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.ARCHIVO
                    (URI_ALMACENAJE, NOMBRE_ORIGINAL, TIPO_MIME, HASH_SHA256, TAMANO_BYTES, FECHA_CREACION)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (HASH_SHA256) DO NOTHING
                RETURNING ID_ARCHIVO
                """,
                (str(ruta), nombre, mime_type, hash_sha256, tamano, fecha_creacion),
            )
            resultado = cur.fetchone()
            if resultado:
                id_archivo = resultado[0]
                logger.debug("Archivo guardado: ID=%s hash=%s", id_archivo, hash_sha256[:8])
                return id_archivo
            else:
                # Ya existía; obtenemos el ID
                cur.execute("SELECT ID_ARCHIVO FROM FACTURACION.ARCHIVO WHERE HASH_SHA256 = %s", (hash_sha256,))
                existente = cur.fetchone()
                return existente[0] if existente else None

    def guardar_correo_entrante(
        self,
        conn: Connection,
        id_mensaje: str,
        remitente: str,
        destinatario: str,
        asunto: Optional[str] = None,
        fecha_recepcion: Optional[datetime] = None,
        fecha_envio: Optional[datetime] = None,
        cuerpo_texto: Optional[str] = None,
        cuerpo_html: Optional[str] = None,
        id_archivo_eml: Optional[int] = None,
    ) -> Optional[int]:
        """Guarda un correo en CORREO_ENTRANTE (sin commit)."""
        if fecha_recepcion is None:
            fecha_recepcion = datetime.now(tz=timezone.utc)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.CORREO_ENTRANTE (
                    ID_MENSAJE_EMAIL, REMITENTE, DESTINATARIO, ASUNTO,
                    FECHA_RECEPCION, FECHA_ENVIO, CUERPO_TEXTO, CUERPO_HTML, ID_ARCHIVO_EML
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ID_MENSAJE_EMAIL) DO NOTHING
                RETURNING ID_CORREO
                """,
                (
                    id_mensaje,
                    remitente,
                    destinatario,
                    asunto,
                    fecha_recepcion,
                    fecha_envio,
                    cuerpo_texto,
                    cuerpo_html,
                    id_archivo_eml,
                ),
            )
            resultado = cur.fetchone()
            if resultado:
                id_correo = resultado[0]
                logger.debug("Correo guardado: ID=%s mensaje=%s", id_correo, id_mensaje)
                return id_correo
            else:
                cur.execute("SELECT ID_CORREO FROM FACTURACION.CORREO_ENTRANTE WHERE ID_MENSAJE_EMAIL = %s", (id_mensaje,))
                existente = cur.fetchone()
                return existente[0] if existente else None

    def guardar_adjunto_correo(
        self,
        conn: Connection,
        id_correo: int,
        id_archivo: int,
        nombre_archivo: str,
        es_zip: bool = False,
        es_xml: bool = False,
        es_comprobante_dian: bool = False,
        orden: int = 1,
    ) -> int:
        """Registra un adjunto en ADJUNTO_CORREO (sin commit)."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.ADJUNTO_CORREO (
                    ID_CORREO, ID_ARCHIVO, NOMBRE_ARCHIVO, ORDEN_ADJUNTO,
                    ES_FORMATO_ZIP, ES_FORMATO_XML, ES_COMPROBANTE_DIAN
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ID_CORREO, ID_ARCHIVO) DO NOTHING
                RETURNING ID_ADJUNTO
                """,
                (id_correo, id_archivo, nombre_archivo, orden, es_zip, es_xml, es_comprobante_dian),
            )
            resultado = cur.fetchone()
            if resultado:
                logger.debug("Adjunto registrado: ID=%s para correo ID=%s", resultado[0], id_correo)
                return resultado[0]
            else:
                cur.execute(
                    "SELECT ID_ADJUNTO FROM FACTURACION.ADJUNTO_CORREO WHERE ID_CORREO = %s AND ID_ARCHIVO = %s",
                    (id_correo, id_archivo),
                )
                existente = cur.fetchone()
                return existente[0] if existente else -1

    def crear_proceso_ingesta(
        self,
        conn: Connection,
        id_correo: int,
        id_adjunto: Optional[int] = None,
        id_archivo_origen: Optional[int] = None,
        cufe_detectado: Optional[str] = None,
    ) -> int:
        """Crea un registro de proceso de ingesta (sin commit)."""
        clave_idempotencia = f"email_{id_correo}_{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S')}"
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.PROCESO_INGESTA (
                    ID_CORREO, ID_ADJUNTO, ID_ARCHIVO_ORIGEN, CLAVE_IDEMPOTENCIA,
                    VERSION_MOTOR, ID_ESTADO_PROCESO, CUFE_DETECTADO
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING ID_PROCESO
                """,
                (
                    id_correo,
                    id_adjunto,
                    id_archivo_origen,
                    clave_idempotencia,
                    "1.0.0",
                    1,  # RECIBIDO
                    cufe_detectado,
                ),
            )
            id_proceso = cur.fetchone()[0]
            logger.debug("Proceso de ingesta creado: ID=%s para correo ID=%s", id_proceso, id_correo)
            return id_proceso

    def actualizar_estado_proceso(
        self,
        conn: Connection,
        id_proceso: int,
        id_estado: int,
        resumen_error: Optional[str] = None,
    ):
        """Actualiza el estado de un proceso de ingesta (sin commit)."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE FACTURACION.PROCESO_INGESTA
                SET ID_ESTADO_PROCESO = %s, RESUMEN_ERROR = %s, FECHA_FIN = NOW()
                WHERE ID_PROCESO = %s
                """,
                (id_estado, resumen_error, id_proceso),
            )
            logger.debug("Proceso ID=%s actualizado a estado %s", id_proceso, id_estado)

    def registrar_log_proceso(
        self,
        conn: Connection,
        id_proceso: int,
        codigo_etapa: str,
        id_estado: int,
        detalle: Optional[dict] = None,
        error: Optional[str] = None,
    ):
        """Registra una entrada en LOG_PROCESO (sin commit)."""
        with conn.cursor() as cur:
            # Obtener siguiente número de secuencia
            cur.execute(
                "SELECT COALESCE(MAX(NUMERO_SECUENCIA), 0) + 1 FROM FACTURACION.LOG_PROCESO WHERE ID_PROCESO = %s",
                (id_proceso,),
            )
            secuencia = cur.fetchone()[0]

            # Convertir detalle (dict) a string JSON para psycopg
            detalle_json = json.dumps(detalle) if detalle else None

            cur.execute(
                """
                INSERT INTO FACTURACION.LOG_PROCESO (
                    ID_PROCESO, NUMERO_SECUENCIA, CODIGO_ETAPA,
                    ID_ESTADO_PROCESO, DETALLE_JSON, DETALLE_ERROR
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (id_proceso, secuencia, codigo_etapa, id_estado, detalle_json, error),
            )
