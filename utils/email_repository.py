"""Repositorio para persistencia de correos y adjuntos en PostgreSQL.

Gestiona la inserción de:
    - Correos entrantes (CORREO_ENTRANTE)
    - Archivos adjuntos (ADJUNTOS_CORREO)
    - Eventos de ingesta (EVENTO_INGESTA)
    - Procesos de ingesta (PROCESO_INGESTA)
    - Relaciones entre ellos

Garantiza idempotencia mediante únicos (MESSAGE_ID, SHA256, CORREO_ID+NOMBRE_ARCHIVO).
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
from metadata.path_s3 import RutasS3

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

    def calcular_hash_sha256(self, ruta_archivo: Path) -> str:
        """Calcula el SHA256 de un archivo."""
        sha256 = hashlib.sha256()
        with ruta_archivo.open("rb") as f:
            for bloque in iter(lambda: f.read(65536), b""):
                sha256.update(bloque)
        return sha256.hexdigest()

    def correo_tiene_adjuntos_exitosos(self, conn: Connection, correo_id: int) -> bool:
        """Verifica si el correo tiene al menos un adjunto seguro registrado.

        Permite distinguir entre:
        - Correo *completamente* procesado (tiene adjuntos) → duplicado real.
        - Correo guardado pero que falló a mitad (ej: ClamAV caído, sin adjuntos)
          → debe reintentarse.

        Args:
            conn: Conexión activa.
            correo_id: ID del correo a verificar.

        Returns:
            True si existe al menos un ADJUNTO con ARCHIVO_SEGURO = TRUE.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM FACTURACION.ADJUNTOS_CORREO
                WHERE CORREO_ID = %s AND ARCHIVO_SEGURO = TRUE
                LIMIT 1
                """,
                (correo_id,),
            )
            return cur.fetchone() is not None

    def existe_adjunto_por_hash(self, conn: Connection, sha256_hash: str) -> bool:
        """Verifica si un adjunto ya existe en BD mediante su hash SHA256."""
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM FACTURACION.ADJUNTOS_CORREO WHERE SHA256 = %s LIMIT 1", (sha256_hash,))
            return cur.fetchone() is not None

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

        hash_sha256 = self.calcular_hash_sha256(ruta)
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
        imap_uid: Optional[int] = None,
    ) -> tuple[Optional[int], bool]:
        """Guarda un correo en CORREO_ENTRANTE (sin commit).
        
        Incluye el IMAP UID para seguimiento de puntero.
        
        Usa el truco ``xmax = 0`` de PostgreSQL para distinguir filas
        recién insertadas (xmax=0) de filas actualizadas por ON CONFLICT
        DO UPDATE (xmax != 0).  Esto es necesario porque RETURNING
        siempre devuelve la fila en ambos casos.
        
        Returns:
            tuple[int, bool]: (CORREO_ID, es_nuevo).
        """
        if fecha_deteccion is None:
            fecha_deteccion = datetime.now(tz=timezone.utc)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.CORREO_ENTRANTE (
                    MESSAGE_ID, REMITENTE, ASUNTO,
                    FECHA_DETECCION, FECHA_ENVIO, CUERPO_TEXTO, CUERPO_HTML,
                    CONTIENE_ADJUNTOS, ID_ORIGEN, IMAP_UID
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (MESSAGE_ID) DO UPDATE SET
                    IMAP_UID = COALESCE(EXCLUDED.IMAP_UID, FACTURACION.CORREO_ENTRANTE.IMAP_UID)
                RETURNING CORREO_ID, (xmax = 0) AS es_nuevo
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
                    imap_uid,
                ),
            )
            resultado = cur.fetchone()
            if resultado:
                id_correo = resultado[0]
                es_nuevo = resultado[1]
                if es_nuevo:
                    logger.debug("Correo NUEVO guardado: ID=%s mensaje=%s", id_correo, id_mensaje)
                else:
                    logger.info(
                        "Correo DUPLICADO detectado (ON CONFLICT): ID=%s mensaje=%s",
                        id_correo, id_mensaje,
                    )
                return id_correo, es_nuevo
            else:
                # Caso teórico: RETURNING no devolvió nada (no debería ocurrir)
                logger.error(
                    "RETURNING vacío para mensaje=%s — recuperando ID manualmente.",
                    id_mensaje,
                )
                cur.execute(
                    "SELECT CORREO_ID FROM FACTURACION.CORREO_ENTRANTE WHERE MESSAGE_ID = %s",
                    (id_mensaje,),
                )
                existente = cur.fetchone()
                return (existente[0] if existente else None), False

    def guardar_adjunto_correo(
        self,
        conn: Connection,
        id_correo: int,
        ruta_archivo: Path,
        id_tipo_archivo: int,
        adjunto_padre_id: Optional[int] = None,
        archivo_seguro: bool = True,
        fecha_envio: Optional[datetime] = None,
    ) -> tuple[int, str]:
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
            fecha_envio: Fecha de envío del correo para construir ruta S3.

        Returns:
            tuple[int, str]: ID del adjunto registrado y su URI de almacenamiento S3.
        """
        id_adjunto = -1
        uri_almacenamiento = ""
        try:
            # Cálculo de metadatos del archivo
            sha256_hash = self.calcular_hash_sha256(ruta_archivo)
            nombre_archivo = ruta_archivo.name
            
            fecha_ref = fecha_envio if fecha_envio else datetime.now(tz=timezone.utc)
            year = fecha_ref.strftime("%Y")
            month = fecha_ref.strftime("%m")
            day = fecha_ref.strftime("%d")
            
            if id_tipo_archivo == 1:
                uri_almacenamiento = RutasS3.zip.format(year=year, month=month, day=day, nombre_descarga=nombre_archivo)
            elif id_tipo_archivo == 2:
                uri_almacenamiento = RutasS3.xml.format(year=year, month=month, day=day, nombre_descarga=nombre_archivo)
            elif id_tipo_archivo == 3:
                uri_almacenamiento = RutasS3.pdf.format(year=year, month=month, day=day, nombre_descarga=nombre_archivo)
            else:
                uri_almacenamiento = str(ruta_archivo)

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

        return id_adjunto, uri_almacenamiento

    # ------------------------------------------------------------------
    # Eventos y Procesos de Ingesta
    # ------------------------------------------------------------------

    def crear_evento_ingesta(
        self,
        conn: Connection,
        adjunto_id: int,
        id_estado: int = 1,
    ) -> bool:
        """Crea un evento de ingesta para un adjunto en EVENTO_INGESTA.

        El evento marca un adjunto como pendiente de procesamiento en el
        pipeline de ingesta.

        Args:
            conn: Conexión activa a la base de datos.
            adjunto_id: ID del adjunto (PK en ADJUNTOS_CORREO).
            id_estado: Estado inicial (default: 1 = PENDIENTE).

        Returns:
            bool: True si se insertó correctamente, False si ya existía o hubo error.
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO FACTURACION.EVENTO_INGESTA
                        (ADJUNTO_ID, ID_ESTADO)
                    VALUES (%s, %s)
                    ON CONFLICT (ADJUNTO_ID) DO NOTHING
                    """,
                    (adjunto_id, id_estado),
                )
                insertado = cur.rowcount > 0
                if insertado:
                    logger.debug("Evento de ingesta creado para ADJUNTO_ID=%s", adjunto_id)
                else:
                    logger.debug("Evento de ingesta ya existente para ADJUNTO_ID=%s", adjunto_id)
                return insertado
        except Exception as err:
            logger.error("Error al crear evento de ingesta para ADJUNTO_ID=%s: %s", adjunto_id, err)
            return False

    def crear_proceso_ingesta(
        self,
        conn: Connection,
        id_proceso: int,
        observacion: str,
        id_estado: int = 1,
        adjunto_id: Optional[int] = None,
        correo_id: Optional[int] = None,
        id_error: Optional[int] = None,
    ) -> int:
        """Crea un registro de proceso de ingesta (sin commit).

        Al menos uno de ``adjunto_id`` o ``correo_id`` debe proporcionarse.
        Usar ``correo_id`` para registros a nivel correo (ej. rechazo sin adjuntos).

        Args:
            conn: Conexión activa a la base de datos.
            id_proceso: Tipo de proceso (FK a TIPO_PROCESO).
            observacion: Descripción del proceso realizado.
            id_estado: Estado del proceso (default: 1 = PENDIENTE).
            adjunto_id: ID del adjunto asociado (None si es a nivel correo).
            correo_id: ID del correo asociado (None si es a nivel adjunto).
            id_error: Tipo de error (FK a TIPO_ERROR), None si no hubo error.

        Returns:
            int: ID del proceso creado, o -1 si hubo error.
        """
        if adjunto_id is None and correo_id is None:
            logger.error("crear_proceso_ingesta requiere adjunto_id o correo_id")
            return -1

        if observacion and len(observacion) > 255:
            observacion = observacion[:252] + '...'

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO FACTURACION.PROCESO_INGESTA (
                        ADJUNTO_ID, CORREO_ID, ID_PROCESO, ID_ESTADO, OBSERVACION, ID_ERROR
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING ID_PROCESO_INGESTA
                    """,
                    (
                        adjunto_id,
                        correo_id,
                        id_proceso,
                        id_estado,
                        observacion,
                        id_error,
                    ),
                )
                id_proceso_ingesta = cur.fetchone()[0]
                ref = f"ADJUNTO_ID={adjunto_id}" if adjunto_id else f"CORREO_ID={correo_id}"
                logger.debug(
                    "Proceso de ingesta creado: ID=%s tipo=%s para %s",
                    id_proceso_ingesta, id_proceso, ref,
                )
                return id_proceso_ingesta
        except Exception as err:
            logger.error(
                "Error al crear proceso de ingesta (adjunto=%s, correo=%s, proceso=%s): %s",
                adjunto_id, correo_id, id_proceso, err,
            )
            return -1

    def actualizar_estado_proceso(
        self,
        conn: Connection,
        id_proceso: int,
        id_estado: int,
        resumen_error: Optional[str] = None,
    ):
        """Actualiza el estado de un proceso de ingesta (sin commit).

        Si se marca como finalizado (procesado o error), actualiza FECHA_FIN.
        """
        if resumen_error and len(resumen_error) > 255:
            resumen_error = resumen_error[:252] + '...'

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE FACTURACION.PROCESO_INGESTA
                SET ID_ESTADO = %s,
                    OBSERVACION = COALESCE(%s, OBSERVACION),
                    FECHA_FIN = CASE WHEN %s IN (3, 4, 5) THEN NOW() ELSE FECHA_FIN END
                WHERE ID_PROCESO_INGESTA = %s
                """,
                (id_estado, resumen_error, id_estado, id_proceso),
            )
            logger.debug("Proceso ID=%s actualizado a estado %s", id_proceso, id_estado)

    def inicializar_factura_control(
        self,
        conn: Connection,
        adjunto_id: int,
        medio_recepcion: str = "CORREO"
    ):
        """Inicializa un registro en FACTURA_CONTROL vinculado al adjunto.
        
        Como la FACTURA aún no se ha creado (el orquestador lo hará luego),
        este registro se utiliza para persistir datos que vienen desde el email.
        """
        with conn.cursor() as cur:
            # Primero verificamos si ya existe por ADJUNTO_ID 
            # (Aunque en el modelo pusimos FK a ID_FACTURA, necesitamos 
            # una forma de persistir el medio de recepción desde la ingesta).
            # Para esto, añadiremos temporalmente el ADJUNTO_ID a FACTURA_CONTROL 
            # o usaremos una lógica de 'best effort' en el orquestador.
            
            # Dado que el usuario pidió que el campo 'Medio en que se recibió' 
            # sea siempre CORREO, podemos manejarlo directamente en el orquestador 
            # evitando cambios complejos en el listener.
            pass

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

    def marcar_correo_procesado(self, conn: Connection, correo_id: int) -> None:
        """Marca el correo en CORREO_ENTRANTE como procesado (PROCESADO = TRUE)."""
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE FACTURACION.CORREO_ENTRANTE SET PROCESADO = TRUE WHERE CORREO_ID = %s",
                (correo_id,)
            )
            logger.debug("Correo ID=%s marcado como procesado", correo_id)

    def guardar_correo_descartado(
        self,
        id_mensaje: str,
        remitente: str,
        asunto: Optional[str],
        motivo: str,
        imap_uid: Optional[int] = None,
        fecha_envio: Optional[datetime] = None,
    ) -> Optional[int]:
        """Registra un correo descartado (no-factura) en BD para excluirlo de reprocesamiento.

        Usa ON CONFLICT (MESSAGE_ID) DO NOTHING para idempotencia.

        Args:
            id_mensaje: Message-ID del correo.
            remitente: Dirección del remitente.
            asunto: Asunto del correo.
            motivo: Motivo del descarte (ej: 'NO_ES_FACTURACION').
            imap_uid: UID IMAP del correo.
            fecha_envio: Fecha de envío del correo.

        Returns:
            CORREO_ID si se insertó, None si ya existía.
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO FACTURACION.CORREO_ENTRANTE (
                            MESSAGE_ID, REMITENTE, ASUNTO,
                            FECHA_DETECCION, FECHA_ENVIO,
                            CONTIENE_ADJUNTOS, ID_ORIGEN, IMAP_UID,
                            MOTIVO_DESCARTE
                        )
                        VALUES (%s, %s, %s, %s, %s, FALSE, 1, %s, %s)
                        ON CONFLICT (MESSAGE_ID) DO NOTHING
                        RETURNING CORREO_ID
                        """,
                        (
                            id_mensaje,
                            remitente,
                            asunto,
                            datetime.now(tz=timezone.utc),
                            fecha_envio,
                            imap_uid,
                            motivo,
                        ),
                    )
                    resultado = cur.fetchone()
                    conn.commit()
                    if resultado:
                        logger.debug(
                            "Correo descartado registrado: ID=%s motivo=%s mensaje=%s",
                            resultado[0], motivo, id_mensaje,
                        )
                        return resultado[0]
                    else:
                        logger.debug(
                            "Correo descartado ya existente en BD: %s", id_mensaje,
                        )
                        return None
        except Exception as err:
            logger.error(
                "Error al registrar correo descartado %s: %s", id_mensaje, err,
            )
            return None

    def existe_correo_descartado(self, conn: Connection, id_mensaje: str) -> bool:
        """Verifica si un correo fue descartado previamente.

        Consulta rápida por MESSAGE_ID + MOTIVO_DESCARTE IS NOT NULL.
        Usado como fallback cuando el flag IMAP custom no funciona.

        Args:
            conn: Conexión activa.
            id_mensaje: Message-ID del correo.

        Returns:
            True si el correo fue descartado.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM FACTURACION.CORREO_ENTRANTE
                WHERE MESSAGE_ID = %s AND MOTIVO_DESCARTE IS NOT NULL
                LIMIT 1
                """,
                (id_mensaje,),
            )
            return cur.fetchone() is not None

    def obtener_message_ids_descartados(self, conn: Connection, imap_uids: list[int]) -> set[int]:
        """Obtiene los IMAP UIDs que corresponden a correos descartados.

        Consulta batch para excluir UIDs de correos previamente descartados.
        Usado como fallback cuando el flag IMAP custom no funciona.

        Args:
            conn: Conexión activa.
            imap_uids: Lista de UIDs IMAP a verificar.

        Returns:
            Set de IMAP UIDs que fueron descartados.
        """
        if not imap_uids:
            return set()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT IMAP_UID FROM FACTURACION.CORREO_ENTRANTE
                WHERE IMAP_UID = ANY(%s) AND MOTIVO_DESCARTE IS NOT NULL
                """,
                (imap_uids,),
            )
            return {row[0] for row in cur.fetchall()}

