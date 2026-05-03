"""Repositorio de persistencia para el procesamiento de facturas electrónicas.

Encapsula las operaciones de base de datos para:
- Consultar XMLs pendientes de procesamiento.
- Verificar idempotencia por CUFE.
- Insertar/actualizar FACTURA, TERCERO y tablas relacionadas.
- Registrar procesos en PROCESO_INGESTA.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Any

import psycopg
from psycopg import Connection

from config import get_postgres_config
from metadata.db_metadata import IdEstadoProceso

logger = logging.getLogger(__name__)


class InvoiceRepository:
    """Repositorio para operaciones de persistencia de facturas."""

    def __init__(self, config: Optional[dict] = None):
        """Inicializa el repositorio.

        Args:
            config: Configuración de BD (si None, se lee de entorno).
        """
        self.config = config or get_postgres_config()

    def get_connection(self) -> Connection:
        """Crea una nueva conexión a la BD."""
        return psycopg.connect(
            host=self.config['host'],
            port=int(self.config['port']),
            dbname=self.config['dbname'],
            user=self.config['user'],
            password=self.config['password'],
        )

    # ------------------------------------------------------------------
    # Consultas de EVENTO_INGESTA
    # ------------------------------------------------------------------

    def obtener_eventos_pendientes(
        self,
        conn: Connection,
        limite: int = 50,
    ) -> list[dict]:
        """Obtiene los EVENTO_INGESTA pendientes con sus datos de adjunto.

        Filtra por ID_ESTADO = PENDIENTE (1) y archivos XML (ID_TIPO_ARCHIVO = 2).
        Agrupa por ADJUNTO_PADRE_ID para procesar familias completas.

        Args:
            conn: Conexión activa.
            limite: Máximo de eventos a retornar.

        Returns:
            Lista de diccionarios con datos del evento y adjunto.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    ei.ADJUNTO_ID,
                    ei.ID_ESTADO,
                    ei.INTENTOS,
                    ac.CORREO_ID,
                    ac.NOMBRE_ARCHIVO,
                    ac.URI_ALMACENAMIENTO,
                    ac.SHA256,
                    ac.ADJUNTO_PADRE_ID,
                    ac.ID_TIPO_ARCHIVO
                FROM FACTURACION.EVENTO_INGESTA ei
                JOIN FACTURACION.ADJUNTOS_CORREO ac ON ei.ADJUNTO_ID = ac.ADJUNTO_ID
                WHERE ei.ID_ESTADO = %s
                  AND ac.ID_TIPO_ARCHIVO = 2
                ORDER BY ei.FECHA_CREACION ASC
                LIMIT %s
                """,
                (IdEstadoProceso.pendiente, limite),
            )
            columnas = [desc[0].lower() for desc in cur.description]
            return [dict(zip(columnas, row)) for row in cur.fetchall()]

    def obtener_adjuntos_hermanos(
        self,
        conn: Connection,
        adjunto_padre_id: int,
    ) -> list[dict]:
        """Obtiene los adjuntos que comparten el mismo padre.

        Args:
            conn: Conexión activa.
            adjunto_padre_id: ID del adjunto padre.

        Returns:
            Lista de diccionarios con datos del adjunto.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ADJUNTO_ID,
                    NOMBRE_ARCHIVO,
                    URI_ALMACENAMIENTO,
                    SHA256,
                    ADJUNTO_PADRE_ID,
                    ID_TIPO_ARCHIVO
                FROM FACTURACION.ADJUNTOS_CORREO
                WHERE ADJUNTO_PADRE_ID = %s
                ORDER BY ADJUNTO_ID ASC
                """,
                (adjunto_padre_id,),
            )
            columnas = [desc[0].lower() for desc in cur.description]
            return [dict(zip(columnas, row)) for row in cur.fetchall()]

    # ------------------------------------------------------------------
    # Estado de eventos y procesos
    # ------------------------------------------------------------------

    def actualizar_estado_evento(
        self,
        conn: Connection,
        adjunto_id: int,
        id_estado: int,
    ) -> None:
        """Actualiza el estado de un EVENTO_INGESTA."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE FACTURACION.EVENTO_INGESTA
                SET ID_ESTADO = %s, FECHA_ACTUALIZACION = NOW()
                WHERE ADJUNTO_ID = %s
                """,
                (id_estado, adjunto_id),
            )

    def incrementar_intentos_evento(
        self,
        conn: Connection,
        adjunto_id: int,
    ) -> int:
        """Incrementa el contador de intentos y retorna el nuevo valor."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE FACTURACION.EVENTO_INGESTA
                SET INTENTOS = INTENTOS + 1
                WHERE ADJUNTO_ID = %s
                RETURNING INTENTOS
                """,
                (adjunto_id,),
            )
            resultado = cur.fetchone()
            return resultado[0] if resultado else 0

    def crear_proceso_ingesta(
        self,
        conn: Connection,
        adjunto_id: int,
        id_proceso: int,
        observacion: str,
        id_estado: int = IdEstadoProceso.procesado,
    ) -> int:
        """Crea un registro en PROCESO_INGESTA.

        Args:
            conn: Conexión activa.
            adjunto_id: ID del adjunto asociado.
            id_proceso: Tipo de proceso (FK a TIPO_PROCESO).
            observacion: Descripción del resultado.
            id_estado: Estado del proceso.

        Returns:
            ID del proceso creado, o -1 si hubo error.
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO FACTURACION.PROCESO_INGESTA (
                        ADJUNTO_ID, ID_PROCESO, ID_ESTADO, OBSERVACION
                    )
                    VALUES (%s, %s, %s, %s)
                    RETURNING ID_PROCESO_INGESTA
                    """,
                    (adjunto_id, id_proceso, id_estado, observacion),
                )
                resultado = cur.fetchone()
                return resultado[0] if resultado else -1
        except Exception as err:
            logger.error(
                'Error al crear PROCESO_INGESTA (adjunto=%s, proceso=%s): %s',
                adjunto_id, id_proceso, err,
            )
            return -1

    # ------------------------------------------------------------------
    # Operaciones de FACTURA
    # ------------------------------------------------------------------

    def buscar_factura_por_cufe(
        self,
        conn: Connection,
        cufe: str,
    ) -> Optional[dict]:
        """Busca una factura existente por su CUFE.

        Args:
            conn: Conexión activa.
            cufe: CUFE a buscar.

        Returns:
            dict con datos de la factura si existe, None si no.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    f.ID_FACTURA,
                    f.CUFE,
                    f.NUMERO_FACTURA,
                    f.ADJUNTO_ID,
                    f.ID_ESTADO_PROCESO,
                    ac.SHA256
                FROM FACTURACION.FACTURA f
                LEFT JOIN FACTURACION.ADJUNTOS_CORREO ac ON f.ADJUNTO_ID = ac.ADJUNTO_ID
                WHERE f.CUFE = %s
                """,
                (cufe,),
            )
            resultado = cur.fetchone()
            if resultado:
                columnas = [desc[0].lower() for desc in cur.description]
                return dict(zip(columnas, resultado))
            return None

    def insertar_factura(
        self,
        conn: Connection,
        datos: dict,
    ) -> int:
        """Inserta una factura en la tabla FACTURA.

        Args:
            conn: Conexión activa.
            datos: Diccionario con los campos de la factura.

        Returns:
            ID de la factura insertada.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.FACTURA (
                    CUFE, DENOMINACION, PREFIJO_FACTURACION, NUMERO_FACTURA,
                    ID_TERCERO_EMISOR, ID_TERCERO_ADQUIRIENTE,
                    ID_AUTORIZACION, FECHA_GENERACION, FECHA_EXPEDICION,
                    FECHA_VENCIMIENTO, CODIGO_MONEDA, VALOR_TOTAL,
                    HASH_FIRMA_DIGITAL, CONTENIDO_QR,
                    ADJUNTO_ID, ID_ESTADO_PROCESO
                )
                VALUES (
                    %(cufe)s, %(denominacion)s, %(prefijo)s, %(numero_factura)s,
                    %(id_tercero_emisor)s, %(id_tercero_adquiriente)s,
                    %(id_autorizacion)s, %(fecha_generacion)s, %(fecha_expedicion)s,
                    %(fecha_vencimiento)s, %(moneda)s, %(valor_total)s,
                    %(hash_firma)s, %(contenido_qr)s,
                    %(adjunto_id)s, %(id_estado_proceso)s
                )
                ON CONFLICT (CUFE) DO UPDATE SET
                    DENOMINACION = EXCLUDED.DENOMINACION,
                    VALOR_TOTAL = EXCLUDED.VALOR_TOTAL,
                    HASH_FIRMA_DIGITAL = EXCLUDED.HASH_FIRMA_DIGITAL,
                    CONTENIDO_QR = EXCLUDED.CONTENIDO_QR,
                    ADJUNTO_ID = EXCLUDED.ADJUNTO_ID,
                    ID_ESTADO_PROCESO = EXCLUDED.ID_ESTADO_PROCESO,
                    FECHA_ACTUALIZACION = NOW()
                RETURNING ID_FACTURA
                """,
                datos,
            )
            resultado = cur.fetchone()
            return resultado[0] if resultado else -1

    # ------------------------------------------------------------------
    # Operaciones de TERCERO
    # ------------------------------------------------------------------

    def upsert_tercero(
        self,
        conn: Connection,
        datos: dict,
    ) -> int:
        """Inserta o actualiza un tercero.

        Args:
            conn: Conexión activa.
            datos: Diccionario con campos del tercero.

        Returns:
            ID del tercero.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.TERCERO (
                    NUMERO_DOCUMENTO, TIPO_DOCUMENTO, DIGITO_VERIFICADOR,
                    RAZON_SOCIAL, NOMBRE_COMERCIAL,
                    CORREO_CONTACTO, TELEFONO_CONTACTO, CODIGO_CIIU
                )
                VALUES (
                    %(numero_documento)s, %(tipo_documento)s, %(digito_verificador)s,
                    %(razon_social)s, %(nombre_comercial)s,
                    %(correo_contacto)s, %(telefono_contacto)s, %(codigo_ciiu)s
                )
                ON CONFLICT (NUMERO_DOCUMENTO) DO UPDATE SET
                    RAZON_SOCIAL = COALESCE(EXCLUDED.RAZON_SOCIAL, FACTURACION.TERCERO.RAZON_SOCIAL),
                    NOMBRE_COMERCIAL = COALESCE(EXCLUDED.NOMBRE_COMERCIAL, FACTURACION.TERCERO.NOMBRE_COMERCIAL),
                    CORREO_CONTACTO = COALESCE(EXCLUDED.CORREO_CONTACTO, FACTURACION.TERCERO.CORREO_CONTACTO),
                    TELEFONO_CONTACTO = COALESCE(EXCLUDED.TELEFONO_CONTACTO, FACTURACION.TERCERO.TELEFONO_CONTACTO)
                RETURNING ID_TERCERO
                """,
                datos,
            )
            resultado = cur.fetchone()
            return resultado[0] if resultado else -1

    # ------------------------------------------------------------------
    # Operaciones de AUTORIZACION_NUMERACION_DIAN
    # ------------------------------------------------------------------

    def upsert_autorizacion(
        self,
        conn: Connection,
        datos: dict,
    ) -> int:
        """Inserta o actualiza una autorización de numeración DIAN.

        Args:
            conn: Conexión activa.
            datos: Diccionario con campos de la autorización.

        Returns:
            ID de la autorización.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.AUTORIZACION_NUMERACION_DIAN (
                    NUMERO_AUTORIZACION, PREFIJO, RANGO_DESDE, RANGO_HASTA,
                    FECHA_INICIO_VIGENCIA, FECHA_FIN_VIGENCIA
                )
                VALUES (
                    %(numero_autorizacion)s, %(prefijo)s, %(rango_desde)s,
                    %(rango_hasta)s, %(fecha_inicio)s, %(fecha_fin)s
                )
                ON CONFLICT (NUMERO_AUTORIZACION) DO UPDATE SET
                    PREFIJO = EXCLUDED.PREFIJO,
                    RANGO_DESDE = EXCLUDED.RANGO_DESDE,
                    RANGO_HASTA = EXCLUDED.RANGO_HASTA
                RETURNING ID_AUTORIZACION
                """,
                datos,
            )
            resultado = cur.fetchone()
            return resultado[0] if resultado else -1

    # ------------------------------------------------------------------
    # Operaciones de tablas de detalle
    # ------------------------------------------------------------------

    def insertar_detalle_factura(
        self,
        conn: Connection,
        id_factura: int,
        linea: dict,
    ) -> int:
        """Inserta una línea de detalle de factura."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.DETALLE_FACTURA (
                    ID_FACTURA, NUMERO_LINEA, DESCRIPCION,
                    CODIGO_PRODUCTO, CANTIDAD, UNIDAD_MEDIDA,
                    VALOR_UNITARIO, VALOR_TOTAL_LINEA
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING ID_DETALLE
                """,
                (
                    id_factura,
                    linea.get('numero_linea'),
                    linea.get('descripcion'),
                    linea.get('codigo_item'),
                    Decimal(linea['cantidad']) if linea.get('cantidad') else None,
                    linea.get('unidad_medida'),
                    Decimal(linea['valor_unitario']) if linea.get('valor_unitario') else None,
                    Decimal(linea['valor_total_linea']) if linea.get('valor_total_linea') else None,
                ),
            )
            resultado = cur.fetchone()
            return resultado[0] if resultado else -1

    def insertar_impuesto_factura(
        self,
        conn: Connection,
        id_factura: int,
        impuesto: dict,
    ) -> int:
        """Inserta un impuesto a nivel de factura."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.IMPUESTO_FACTURA (
                    ID_FACTURA, CODIGO_IMPUESTO, NOMBRE_IMPUESTO,
                    BASE_GRAVABLE, TARIFA, VALOR_IMPUESTO
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING ID_IMPUESTO_FACTURA
                """,
                (
                    id_factura,
                    impuesto.get('codigo_impuesto'),
                    impuesto.get('nombre_impuesto'),
                    Decimal(impuesto['base_gravable']) if impuesto.get('base_gravable') else None,
                    Decimal(impuesto['tarifa']) if impuesto.get('tarifa') else None,
                    Decimal(impuesto['valor_impuesto']) if impuesto.get('valor_impuesto') else None,
                ),
            )
            resultado = cur.fetchone()
            return resultado[0] if resultado else -1

    def insertar_pago_factura(
        self,
        conn: Connection,
        id_factura: int,
        datos_pago: dict,
    ) -> int:
        """Inserta los datos de pago de la factura."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.PAGO_FACTURA (
                    ID_FACTURA, CODIGO_FORMA_PAGO, CODIGO_MEDIO_PAGO,
                    FECHA_VENCIMIENTO, DURACION_PLAZO
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING ID_PAGO
                """,
                (
                    id_factura,
                    datos_pago.get('codigo_forma_pago'),
                    datos_pago.get('codigo_medio_pago'),
                    datos_pago.get('fecha_vencimiento'),
                    datos_pago.get('duracion_plazo'),
                ),
            )
            resultado = cur.fetchone()
            return resultado[0] if resultado else -1

    def insertar_condicion_fiscal(
        self,
        conn: Connection,
        id_factura: int,
        id_tercero: int,
        tipo_tercero: str,
        responsabilidades: list[dict],
    ) -> None:
        """Inserta las condiciones fiscales de un tercero en la factura."""
        with conn.cursor() as cur:
            for resp in responsabilidades:
                cur.execute(
                    """
                    INSERT INTO FACTURACION.CONDICION_FISCAL_FACTURA (
                        ID_FACTURA, ID_TERCERO, TIPO_TERCERO,
                        CODIGO_RESPONSABILIDAD, DESCRIPCION_RESPONSABILIDAD
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        id_factura,
                        id_tercero,
                        tipo_tercero,
                        resp.get('codigo'),
                        resp.get('descripcion'),
                    ),
                )

    def marcar_evento_procesado(
        self,
        conn: Connection,
        adjunto_id: int,
        id_estado: int = IdEstadoProceso.procesado,
    ) -> None:
        """Marca el EVENTO_INGESTA asociado como procesado."""
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE FACTURACION.EVENTO_INGESTA
                SET ID_ESTADO = %s, FECHA_ACTUALIZACION = NOW()
                WHERE ADJUNTO_ID = %s
                """,
                (id_estado, adjunto_id),
            )
