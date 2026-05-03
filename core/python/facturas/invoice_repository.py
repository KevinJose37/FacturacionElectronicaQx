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
        Calcula también ADJUNTO_RAIZ_ID recorriendo la cadena de padres hasta
        encontrar el ancestro más alto. Esto permite agrupar la familia completa
        (AttachedDocument + Invoice + ApplicationResponse) bajo una misma raíz
        aunque la jerarquía tenga varios niveles.

        Args:
            conn: Conexión activa.
            limite: Máximo de eventos a retornar.

        Returns:
            Lista de diccionarios con datos del evento, del adjunto y la raíz.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH RECURSIVE arbol AS (
                    -- Caso base: cada adjunto se apunta a sí mismo
                    SELECT
                        ADJUNTO_ID,
                        ADJUNTO_PADRE_ID,
                        ADJUNTO_ID AS ADJUNTO_RAIZ_ID
                    FROM FACTURACION.ADJUNTOS_CORREO
                    WHERE ADJUNTO_PADRE_ID IS NULL

                    UNION ALL

                    -- Recursivo: hereda la raíz del padre
                    SELECT
                        hijo.ADJUNTO_ID,
                        hijo.ADJUNTO_PADRE_ID,
                        padre.ADJUNTO_RAIZ_ID
                    FROM FACTURACION.ADJUNTOS_CORREO hijo
                    JOIN arbol padre ON hijo.ADJUNTO_PADRE_ID = padre.ADJUNTO_ID
                )
                SELECT
                    ei.ADJUNTO_ID,
                    ei.ID_ESTADO,
                    ei.INTENTOS,
                    ac.CORREO_ID,
                    ac.NOMBRE_ARCHIVO,
                    ac.URI_ALMACENAMIENTO,
                    ac.SHA256,
                    ac.ADJUNTO_PADRE_ID,
                    ac.ID_TIPO_ARCHIVO,
                    arbol.ADJUNTO_RAIZ_ID
                FROM FACTURACION.EVENTO_INGESTA ei
                JOIN FACTURACION.ADJUNTOS_CORREO ac ON ei.ADJUNTO_ID = ac.ADJUNTO_ID
                LEFT JOIN arbol ON ei.ADJUNTO_ID = arbol.ADJUNTO_ID
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
                    (adjunto_id, id_proceso, id_estado, observacion[:255]),
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
                    ID_ROL_TERCERO, NUMERO_DOCUMENTO, DIGITO_VERIFICADOR,
                    RAZON_SOCIAL, NOMBRE_COMERCIAL,
                    CORREO_CONTACTO, TELEFONO_CONTACTO
                )
                VALUES (
                    %(id_rol_tercero)s, %(numero_documento)s, %(digito_verificador)s,
                    %(razon_social)s, %(nombre_comercial)s,
                    %(correo_contacto)s, %(telefono_contacto)s
                )
                ON CONFLICT (ID_ROL_TERCERO, NUMERO_DOCUMENTO) DO UPDATE SET
                    DIGITO_VERIFICADOR = COALESCE(EXCLUDED.DIGITO_VERIFICADOR, FACTURACION.TERCERO.DIGITO_VERIFICADOR),
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
            # Buscar autorización existente por (emisor, resolución)
            cur.execute(
                """
                SELECT ID_AUTORIZACION
                FROM FACTURACION.AUTORIZACION_NUMERACION_DIAN
                WHERE ID_TERCERO_EMISOR = %(id_tercero_emisor)s
                  AND NUMERO_RESOLUCION = %(numero_resolucion)s
                LIMIT 1
                """,
                datos,
            )
            existente = cur.fetchone()
            if existente:
                return existente[0]

            cur.execute(
                """
                INSERT INTO FACTURACION.AUTORIZACION_NUMERACION_DIAN (
                    ID_TERCERO_EMISOR, PREFIJO_FACTURACION, NUMERO_RESOLUCION,
                    RANGO_DESDE, RANGO_HASTA,
                    FECHA_AUTORIZACION, FECHA_INICIO_VIGENCIA, FECHA_FIN_VIGENCIA
                )
                VALUES (
                    %(id_tercero_emisor)s, %(prefijo_facturacion)s, %(numero_resolucion)s,
                    %(rango_desde)s, %(rango_hasta)s,
                    %(fecha_autorizacion)s, %(fecha_inicio_vigencia)s, %(fecha_fin_vigencia)s
                )
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
        cantidad = Decimal(str(linea['cantidad'])) if linea.get('cantidad') else Decimal('1')
        if cantidad <= 0:
            cantidad = Decimal('1')
        valor_unit = Decimal(str(linea['valor_unitario'])) if linea.get('valor_unitario') else Decimal('0')
        if valor_unit < 0:
            valor_unit = Decimal('0')
        valor_total = Decimal(str(linea['valor_total_linea'])) if linea.get('valor_total_linea') else Decimal('0')
        if valor_total < 0:
            valor_total = Decimal('0')

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.DETALLE_FACTURA (
                    ID_FACTURA, NUMERO_LINEA, CODIGO_ITEM, DESCRIPCION_ITEM,
                    CANTIDAD, UNIDAD_DE_MEDIDA,
                    VALOR_UNITARIO, VALOR_TOTAL_LINEA
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ID_FACTURA, NUMERO_LINEA) DO NOTHING
                RETURNING ID_DETALLE
                """,
                (
                    id_factura,
                    linea.get('numero_linea') or 1,
                    linea.get('codigo_item'),
                    linea.get('descripcion') or 'Sin descripción',
                    cantidad,
                    linea.get('unidad_medida'),
                    valor_unit,
                    valor_total,
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
        # Mapeo de códigos DIAN a IDs de TIPO_IMPUESTO
        mapa_impuesto = {
            '01': 1, 'IVA': 1,
            '04': 2, 'INC': 2,
            '22': 3, 'INC_BOLSAS': 3,
        }
        codigo = (impuesto.get('codigo_impuesto') or '').upper()
        nombre = (impuesto.get('nombre_impuesto') or '').upper()
        id_impuesto = mapa_impuesto.get(codigo) or mapa_impuesto.get(nombre) or 1

        base = Decimal(str(impuesto['base_gravable'])) if impuesto.get('base_gravable') else Decimal('0')
        if base < 0:
            base = Decimal('0')
        tarifa = Decimal(str(impuesto['tarifa'])) if impuesto.get('tarifa') is not None else Decimal('0')
        if tarifa < 0:
            tarifa = Decimal('0')
        valor = Decimal(str(impuesto['valor_impuesto'])) if impuesto.get('valor_impuesto') else Decimal('0')
        if valor < 0:
            valor = Decimal('0')

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.IMPUESTO_FACTURA (
                    ID_FACTURA, ID_IMPUESTO, TARIFA, BASE_GRAVABLE, VALOR_IMPUESTO
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (ID_FACTURA, ID_IMPUESTO, TARIFA) DO NOTHING
                """,
                (id_factura, id_impuesto, tarifa, base, valor),
            )
            return id_impuesto

    def insertar_pago_factura(
        self,
        conn: Connection,
        id_factura: int,
        datos_pago: dict,
    ) -> int:
        """Inserta los datos de pago de la factura."""
        # Mapeo de códigos DIAN a IDs internos
        cf_raw = str(datos_pago.get('codigo_forma_pago') or '').strip()
        try:
            id_forma = int(cf_raw) if cf_raw in ('1', '2') else 1
        except (TypeError, ValueError):
            id_forma = 1  # CONTADO por defecto

        # Si es CONTADO, el medio de pago es obligatorio (default: OTRO=5)
        cm_raw = str(datos_pago.get('codigo_medio_pago') or '').strip()
        try:
            id_medio = int(cm_raw) if cm_raw.isdigit() and 1 <= int(cm_raw) <= 5 else None
        except (TypeError, ValueError):
            id_medio = None
        if id_forma == 1 and id_medio is None:
            id_medio = 5  # OTRO

        plazo = datos_pago.get('duracion_plazo')
        try:
            plazo = int(plazo) if plazo is not None else None
            if plazo is not None and plazo < 0:
                plazo = None
        except (TypeError, ValueError):
            plazo = None

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.PAGO_FACTURA (
                    ID_FACTURA, ID_FORMA_PAGO, ID_MEDIO_PAGO, PLAZO_EN_DIAS
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (ID_FACTURA) DO NOTHING
                """,
                (id_factura, id_forma, id_medio, plazo),
            )
            return id_factura

    def insertar_condicion_fiscal(
        self,
        conn: Connection,
        id_factura: int,
        id_tercero: int,
        tipo_tercero: str,
        responsabilidades: list[dict],
    ) -> None:
        """Inserta las condiciones fiscales de un tercero en la factura."""
        # Mapeo de códigos de responsabilidad DIAN a IDs de TIPO_CONDICION_FISCAL
        mapa_cond = {
            'O-11': 1, 'AGENTE_RETENEDOR_IVA': 1,
            'O-15': 2, 'AUTORRETENEDOR_RENTA': 2, 'O-23': 2,
            'O-13': 3, 'GRAN_CONTRIBUYENTE': 3,
            'O-47': 4, 'SIMPLE': 4,
        }
        with conn.cursor() as cur:
            for resp in responsabilidades:
                codigo = (resp.get('codigo') or '').upper().strip()
                id_cond = mapa_cond.get(codigo)
                if id_cond is None:
                    continue  # responsabilidad sin mapeo, se omite

                nota = (resp.get('descripcion') or '')[:300] or None
                if tipo_tercero:
                    prefijo = f'[{tipo_tercero} id={id_tercero}] '
                    nota = (prefijo + (nota or ''))[:300]

                cur.execute(
                    """
                    INSERT INTO FACTURACION.CONDICION_FISCAL_FACTURA (
                        ID_FACTURA, ID_CONDICION_FISCAL, ES_APLICABLE, NOTAS_ADICIONALES
                    )
                    VALUES (%s, %s, TRUE, %s)
                    ON CONFLICT (ID_FACTURA, ID_CONDICION_FISCAL) DO NOTHING
                    """,
                    (id_factura, id_cond, nota),
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
