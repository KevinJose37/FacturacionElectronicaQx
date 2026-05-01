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
        asunto: Optional[str] = None,
        fecha_deteccion: Optional[datetime] = None,
        fecha_envio: Optional[datetime] = None,
        cuerpo_texto: Optional[str] = None,
        cuerpo_html: Optional[str] = None,
        contiene_adjuntos: bool = False,
        id_origen: int = 1,
    ) -> Optional[int]:
        """Guarda un correo en CORREO_ENTRANTE (sin commit)."""
        if fecha_deteccion is None:
            fecha_deteccion = datetime.now(tz=timezone.utc)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.CORREO_ENTRANTE (
                    MESSAGE_ID, REMITENTE, ASUNTO,
                    FECHA_DETECCION, FECHA_ENVIO, CUERPO_TEXTO, CUERPO_HTML,
                    CONTIENE_ADJUNTOS, ID_ORIGEN
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (MESSAGE_ID) DO NOTHING
                RETURNING CORREO_ID
                """,
                (
                    id_mensaje,
                    remitente,
                    asunto,
                    fecha_deteccion,
                    fecha_envio,
                    cuerpo_texto,
                    cuerpo_html,
                    contiene_adjuntos,
                    id_origen,
                ),
            )
            resultado = cur.fetchone()
            if resultado:
                id_correo = resultado[0]
                logger.debug("Correo guardado: ID=%s mensaje=%s", id_correo, id_mensaje)
                return id_correo
            else:
                cur.execute("SELECT CORREO_ID FROM FACTURACION.CORREO_ENTRANTE WHERE MESSAGE_ID = %s", (id_mensaje,))
                existente = cur.fetchone()
                return existente[0] if existente else None

    def guardar_adjunto_correo(
        self,
        conn: Connection,
        id_correo: int,
        ruta_archivo: Path,
        id_tipo_archivo: int,
        adjunto_padre_id: Optional[int] = None,
        archivo_seguro: bool = True,
    ) -> int:
        """Guarda un adjunto en la tabla ADJUNTOS_CORREO.

        Gestiona la persistencia de metadatos de archivos adjuntos, incluyendo
        el hash SHA256 y la jerarquía de archivos.

        Args:
            conn: Conexión activa a la base de datos.
            id_correo: ID del correo asociado (CORREO_ID).
            ruta_archivo: Ruta del archivo en el sistema de archivos.
            id_tipo_archivo: Identificador del tipo de archivo.
            adjunto_padre_id: ID del adjunto raíz (para agrupar hijos).
            archivo_seguro: Indica si el archivo es confiable.

        Returns:
            int: ID del adjunto registrado o el ID existente en caso de conflicto.
        """
        id_adjunto = -1
        try:
            # Cálculo de metadatos del archivo
            sha256_hash = self._calcular_hash_sha256(ruta_archivo)
            uri_almacenamiento = str(ruta_archivo)
            nombre_archivo = ruta_archivo.name

            with conn.cursor() as cur:
                # Intento de inserción respetando el esquema solicitado
                cur.execute(
                    """
                    INSERT INTO FACTURACION.ADJUNTOS_CORREO (
                        CORREO_ID, ADJUNTO_PADRE_ID, NOMBRE_ARCHIVO,
                        ID_TIPO_ARCHIVO, URI_ALMACENAMIENTO, SHA256, ARCHIVO_SEGURO
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (CORREO_ID, NOMBRE_ARCHIVO) DO NOTHING
                    RETURNING ADJUNTO_ID
                    """,
                    (
                        id_correo,
                        adjunto_padre_id,
                        nombre_archivo,
                        id_tipo_archivo,
                        uri_almacenamiento,
                        sha256_hash,
                        archivo_seguro,
                    ),
                )
                
                res = cur.fetchone()
                if res:
                    id_adjunto = res[0]
                    
                    # Autorreferencia para archivos raíz (ZIP) para compartir el mismo PADRE_ID
                    if adjunto_padre_id is None:
                        cur.execute(
                            "UPDATE FACTURACION.ADJUNTOS_CORREO SET ADJUNTO_PADRE_ID = %s WHERE ADJUNTO_ID = %s",
                            (id_adjunto, id_adjunto)
                        )
                else:
                    # Si hubo conflicto, recuperamos el ID existente
                    cur.execute(
                        "SELECT ADJUNTO_ID FROM FACTURACION.ADJUNTOS_CORREO WHERE CORREO_ID = %s AND NOMBRE_ARCHIVO = %s",
                        (id_correo, nombre_archivo)
                    )
                    existente = cur.fetchone()
                    id_adjunto = existente[0] if existente else -1

                logger.debug("Adjunto procesado (ID=%s): %s", id_adjunto, nombre_archivo)
                
        except Exception as err:
            logger.error("Error crítico al guardar adjunto %s: %s", ruta_archivo, err)
            id_adjunto = -1

        return id_adjunto

    def crear_proceso_ingesta(
        self,
        conn: Connection,
        id_correo: int,
        id_adjunto: Optional[int] = None,
        id_archivo_origen: Optional[int] = None,
        cufe_detectado: Optional[str] = None,
    ) -> int:
        """Crea un registro de proceso de ingesta (sin commit)."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.PROCESO_INGESTA (
                    ADJUNTO_ID, ID_ESTADO
                )
                VALUES (%s, %s)
                RETURNING ID_PROCESO_INGESTA
                """,
                (
                    id_adjunto,
                    1,  # RECIBIDO
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
                SET ID_ESTADO = %s, OBSERVACION = %s, FECHA_FIN = NOW()
                WHERE ID_PROCESO_INGESTA = %s
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
