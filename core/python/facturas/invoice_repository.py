"""Repositorio de persistencia para el procesamiento de facturas electrónicas.

Encapsula las operaciones de base de datos para:
- Consultar XMLs pendientes de procesamiento.
- Verificar idempotencia por CUFE.
- Insertar/actualizar FACTURA, TERCERO y tablas relacionadas.
- Registrar procesos en PROCESO_INGESTA.
"""
# Standard library imports
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Any

# Third-party imports
import psycopg
from psycopg import Connection

# Local application imports
from config import get_postgres_config
from metadata.db_metadata import (
    IdEstadoProceso,
    IdFormaPago,
    IdMedioPago,
    IdResponsabilidadFiscal,
)

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
    ) -> list:
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
                    WHERE ADJUNTO_PADRE_ID IS NULL OR ADJUNTO_PADRE_ID = ADJUNTO_ID

                    UNION ALL

                    -- Recursivo: hereda la raíz del padre
                    SELECT
                        hijo.ADJUNTO_ID,
                        hijo.ADJUNTO_PADRE_ID,
                        padre.ADJUNTO_RAIZ_ID
                    FROM FACTURACION.ADJUNTOS_CORREO hijo
                    JOIN arbol padre ON hijo.ADJUNTO_PADRE_ID = padre.ADJUNTO_ID
                    WHERE hijo.ADJUNTO_ID != padre.ADJUNTO_ID
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
                  AND ac.ID_TIPO_ARCHIVO IN (2, 3)
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
    ) -> list:
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

    def obtener_adjuntos_familia(
        self,
        conn: Connection,
        adjunto_id: int,
    ) -> list:
        """Obtiene todos los adjuntos de la familia a la que pertenece `adjunto_id`.

        Sube por la cadena de padres hasta la raíz y luego baja recursivamente
        para devolver todos los descendientes (incluyendo la raíz).

        Args:
            conn: Conexión activa.
            adjunto_id: ID de cualquier adjunto de la familia (típicamente el
                XML Invoice asociado a la factura).

        Returns:
            Lista de diccionarios con datos del adjunto (incluye uri, tipo y nombre).
        """
        with conn.cursor() as cur:
            # La familia de un adjunto = todos los adjuntos del mismo CORREO_ID.
            # Es más simple y robusto que recorrer el árbol padre/hijo, y cubre
            # los casos con autorreferencia en la raíz (ZIP padre con
            # ADJUNTO_PADRE_ID = ADJUNTO_ID) sin riesgo de loops.
            cur.execute(
                """
                SELECT
                    ADJUNTO_ID,
                    ADJUNTO_PADRE_ID,
                    CORREO_ID,
                    NOMBRE_ARCHIVO,
                    URI_ALMACENAMIENTO,
                    ID_TIPO_ARCHIVO,
                    SHA256
                FROM FACTURACION.ADJUNTOS_CORREO
                WHERE CORREO_ID = (
                    SELECT CORREO_ID
                    FROM FACTURACION.ADJUNTOS_CORREO
                    WHERE ADJUNTO_ID = %s
                )
                ORDER BY ID_TIPO_ARCHIVO, ADJUNTO_ID
                """,
                (adjunto_id,),
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
        id_error: Optional[int] = None,
    ) -> int:
        """Crea un registro en PROCESO_INGESTA.

        Args:
            conn: Conexión activa.
            adjunto_id: ID del adjunto asociado.
            id_proceso: Tipo de proceso (FK a TIPO_PROCESO).
            observacion: Descripción del resultado.
            id_estado: Estado del proceso.
            id_error: Tipo de error (FK a TIPO_ERROR), opcional.

        Returns:
            ID del proceso creado, o -1 si hubo error.
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO FACTURACION.PROCESO_INGESTA (
                        ADJUNTO_ID, ID_PROCESO, ID_ESTADO, OBSERVACION, ID_ERROR
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING ID_PROCESO_INGESTA
                    """,
                    (adjunto_id, id_proceso, id_estado, observacion[:255], id_error),
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
                    CUFE, DENOMINACION, CODIGO_TIPO_DOCUMENTO_DIAN,
                    PREFIJO_FACTURACION, NUMERO_FACTURA,
                    ID_TERCERO_EMISOR, RAZON_SOCIAL_EMISOR, ID_TERCERO_ADQUIRIENTE, RAZON_SOCIAL_ADQUIRIENTE,
                    ID_AUTORIZACION, FECHA_GENERACION, FECHA_EXPEDICION,
                    FECHA_VENCIMIENTO, CODIGO_MONEDA, VALOR_TOTAL,
                    HASH_FIRMA_DIGITAL, CONTENIDO_QR,
                    ADJUNTO_ID, ID_ESTADO_PROCESO
                )
                VALUES (
                    %(cufe)s, %(denominacion)s, %(codigo_tipo_documento_dian)s,
                    %(prefijo)s, %(numero_factura)s,
                    %(id_tercero_emisor)s, %(razon_social_emisor)s, %(id_tercero_adquiriente)s, %(razon_social_adquiriente)s,
                    %(id_autorizacion)s, %(fecha_generacion)s, %(fecha_expedicion)s,
                    %(fecha_vencimiento)s, %(moneda)s, %(valor_total)s,
                    %(hash_firma)s, %(contenido_qr)s,
                    %(adjunto_id)s, %(id_estado_proceso)s
                )
                ON CONFLICT (CUFE) DO UPDATE SET
                    DENOMINACION = EXCLUDED.DENOMINACION,
                    CODIGO_TIPO_DOCUMENTO_DIAN = EXCLUDED.CODIGO_TIPO_DOCUMENTO_DIAN,
                    RAZON_SOCIAL_EMISOR = EXCLUDED.RAZON_SOCIAL_EMISOR,
                    RAZON_SOCIAL_ADQUIRIENTE = EXCLUDED.RAZON_SOCIAL_ADQUIRIENTE,
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

    def vincular_pdf_a_factura(
        self,
        conn: Connection,
        cufe: str,
        id_adjunto_pdf: int,
    ) -> bool:
        """Vincula un PDF huérfano a una factura existente.

        Busca la factura por su CUFE, obtiene el ID del adjunto principal (XML) y el ID del correo,
        y actualiza el registro del PDF en ADJUNTOS_CORREO para que su padre sea el XML
        y pertenezca al mismo correo. Esto efectivamente unifica la familia.

        Args:
            conn: Conexión activa.
            cufe: CUFE de la factura a buscar.
            id_adjunto_pdf: ID del PDF huérfano.

        Returns:
            True si se vinculó exitosamente, False si no existe la factura.
        """
        with conn.cursor() as cur:
            # Encontrar el ADJUNTO_ID y CORREO_ID original de la factura
            cur.execute(
                """
                SELECT f.ADJUNTO_ID, ac.CORREO_ID 
                FROM FACTURACION.FACTURA f
                JOIN FACTURACION.ADJUNTOS_CORREO ac ON f.ADJUNTO_ID = ac.ADJUNTO_ID
                WHERE f.CUFE = %s
                """,
                (cufe,)
            )
            row = cur.fetchone()
            if not row:
                return False
                
            id_adjunto_xml, id_correo = row
            
            # Actualizar el PDF para que sea hijo del XML y tenga el mismo CORREO_ID
            cur.execute(
                """
                UPDATE FACTURACION.ADJUNTOS_CORREO
                SET ADJUNTO_PADRE_ID = %s,
                    CORREO_ID = %s
                WHERE ADJUNTO_ID = %s
                """,
                (id_adjunto_xml, id_correo, id_adjunto_pdf)
            )
            return cur.rowcount > 0

    def obtener_datos_completos_factura(self, conn: Connection, cufe: str) -> Optional[dict]:
        """Obtiene un diccionario con los datos más importantes de la factura.
        
        Se utiliza principalmente para proveerle contexto al LLM durante la verificación gráfica.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    f.ID_FACTURA,
                    f.CUFE,
                    f.DENOMINACION,
                    f.PREFIJO_FACTURACION,
                    f.NUMERO_FACTURA,
                    f.FECHA_GENERACION,
                    f.VALOR_TOTAL,
                    f.HASH_FIRMA_DIGITAL,
                    emisor.NUMERO_DOCUMENTO as NIT_EMISOR,
                    f.RAZON_SOCIAL_EMISOR as NOMBRE_EMISOR,
                    adq.NUMERO_DOCUMENTO as NIT_ADQUIRIENTE,
                    f.RAZON_SOCIAL_ADQUIRIENTE as NOMBRE_ADQUIRIENTE,
                    auth.NUMERO_RESOLUCION as RESOLUCION_DIAN,
                    (SELECT CODIGO_FORMA_PAGO FROM FACTURACION.PAGO_FACTURA WHERE ID_FACTURA = f.ID_FACTURA LIMIT 1) as FORMA_PAGO,
                    (SELECT CODIGO_MEDIO_PAGO FROM FACTURACION.PAGO_FACTURA WHERE ID_FACTURA = f.ID_FACTURA LIMIT 1) as MEDIO_PAGO,
                    (SELECT STRING_AGG(CODIGO_RESPONSABILIDAD, ', ') FROM FACTURACION.CONDICION_FISCAL_FACTURA WHERE ID_FACTURA = f.ID_FACTURA) as CALIDAD_TRIBUTARIA,
                    (SELECT SUM(VALOR_IMPUESTO) FROM FACTURACION.IMPUESTO_FACTURA WHERE ID_FACTURA = f.ID_FACTURA AND CODIGO_IMPUESTO = '01') as VALOR_IVA,
                    (SELECT fs.RAZON_SOCIAL || ' / ' || ps.NOMBRE_SOFTWARE 
                     FROM FACTURACION.SOFTWARE_FACTURA sf 
                     JOIN FACTURACION.PRODUCTO_SOFTWARE ps ON sf.ID_PRODUCTO_SOFTWARE = ps.ID_PRODUCTO_SOFTWARE 
                     JOIN FACTURACION.FABRICANTE_SOFTWARE fs ON ps.ID_FABRICANTE_SOFTWARE = fs.ID_FABRICANTE_SOFTWARE 
                     WHERE sf.ID_FACTURA = f.ID_FACTURA LIMIT 1) as INFORMACION_SOFTWARE,
                    (SELECT STRING_AGG(CODIGO_FORMA_PAGO || ' / ' || COALESCE(CODIGO_MEDIO_PAGO, ''), ', ') 
                     FROM FACTURACION.PAGO_FACTURA WHERE ID_FACTURA = f.ID_FACTURA) as PAGOS
                FROM FACTURACION.FACTURA f
                LEFT JOIN FACTURACION.TERCERO emisor ON f.ID_TERCERO_EMISOR = emisor.ID_TERCERO
                LEFT JOIN FACTURACION.TERCERO adq ON f.ID_TERCERO_ADQUIRIENTE = adq.ID_TERCERO
                LEFT JOIN FACTURACION.AUTORIZACION_NUMERACION_DIAN auth ON f.ID_AUTORIZACION = auth.ID_AUTORIZACION
                WHERE f.CUFE = %s
                """,
                (cufe,)
            )
            row = cur.fetchone()
            if not row:
                return None
            columnas = [desc[0].lower() for desc in cur.description]
            datos = dict(zip(columnas, row))
            # Mapeos de compatibilidad para el verificador gráfico
            datos['razon_social_emisor'] = datos.get('nombre_emisor')
            datos['razon_social_adquiriente'] = datos.get('nombre_adquiriente')
            datos['fecha_hora_generacion'] = datos.get('fecha_generacion')

            # Obtener detalles de factura
            cur.execute(
                """
                SELECT DESCRIPCION_ITEM, CANTIDAD, VALOR_UNITARIO, VALOR_TOTAL_LINEA
                FROM FACTURACION.DETALLE_FACTURA
                WHERE ID_FACTURA = (SELECT ID_FACTURA FROM FACTURACION.FACTURA WHERE CUFE = %s)
                """,
                (cufe,)
            )
            datos['lineas'] = [dict(zip(['descripcion', 'cantidad', 'valor_unitario', 'valor_total'], r)) for r in cur.fetchall()]
            
            # Formatear fechas e importes para json
            if datos.get('fecha_generacion'):
                datos['fecha_generacion'] = datos['fecha_generacion'].isoformat()
            if datos.get('valor_total') is not None:
                datos['valor_total'] = float(datos['valor_total'])
            
            for linea in datos.get('lineas', []):
                linea['cantidad'] = float(linea['cantidad'])
                linea['valor_unitario'] = float(linea['valor_unitario'])
                linea['valor_total'] = float(linea['valor_total'])

            return datos

    # ------------------------------------------------------------------
    # Operaciones de FACTURA_CONTROL
    # ------------------------------------------------------------------

    def upsert_factura_control(
        self,
        conn: Connection,
        datos: dict,
    ) -> int:
        """Inserta o actualiza los datos de control de una factura.

        Args:
            conn: Conexión activa.
            datos: Diccionario con campos de control.

        Returns:
            ID del registro de control.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.FACTURA_CONTROL (
                    ID_FACTURA, FECHA_ADMISION_PROVEEDOR, MEDIO_RECEPCION,
                    NOMBRE_PROVEEDOR, NIT_PROVEEDOR, NUMERO_FACTURA, FORMA_PAGO
                )
                VALUES (
                    %(id_factura)s, %(fecha_admision_proveedor)s, %(medio_recepcion)s,
                    %(nombre_proveedor)s, %(nit_proveedor)s, %(numero_factura)s, %(forma_pago)s
                )
                ON CONFLICT (ID_FACTURA) DO UPDATE SET
                    FECHA_ADMISION_PROVEEDOR = EXCLUDED.FECHA_ADMISION_PROVEEDOR,
                    NOMBRE_PROVEEDOR = EXCLUDED.NOMBRE_PROVEEDOR,
                    NIT_PROVEEDOR = EXCLUDED.NIT_PROVEEDOR,
                    NUMERO_FACTURA = EXCLUDED.NUMERO_FACTURA,
                    FORMA_PAGO = EXCLUDED.FORMA_PAGO,
                    FECHA_ACTUALIZACION = NOW()
                RETURNING ID_CONTROL
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
                    CORREO_CONTACTO, TELEFONO_CONTACTO,
                    ID_TIPO_DOCUMENTO
                )
                VALUES (
                    %(id_rol_tercero)s, %(numero_documento)s, %(digito_verificador)s,
                    %(correo_contacto)s, %(telefono_contacto)s,
                    %(id_tipo_documento)s
                )
                ON CONFLICT (ID_ROL_TERCERO, NUMERO_DOCUMENTO) DO UPDATE SET
                    DIGITO_VERIFICADOR = COALESCE(EXCLUDED.DIGITO_VERIFICADOR, FACTURACION.TERCERO.DIGITO_VERIFICADOR),
                    CORREO_CONTACTO = COALESCE(EXCLUDED.CORREO_CONTACTO, FACTURACION.TERCERO.CORREO_CONTACTO),
                    TELEFONO_CONTACTO = COALESCE(EXCLUDED.TELEFONO_CONTACTO, FACTURACION.TERCERO.TELEFONO_CONTACTO),
                    ID_TIPO_DOCUMENTO = COALESCE(EXCLUDED.ID_TIPO_DOCUMENTO, FACTURACION.TERCERO.ID_TIPO_DOCUMENTO)
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
        from metadata.db_metadata import IdTipoImpuesto

        codigo = (impuesto.get('codigo_impuesto') or '').strip()
        if not IdTipoImpuesto.es_codigo_valido(codigo):
            # Código no reconocido: registrar como 'ZZ' (Otros)
            logger.warning(
                'Código de impuesto "%s" no reconocido, usando ZZ (Otros).',
                codigo,
            )
            codigo = IdTipoImpuesto.otros

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
                    ID_FACTURA, CODIGO_IMPUESTO, TARIFA, BASE_GRAVABLE, VALOR_IMPUESTO
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (ID_FACTURA, CODIGO_IMPUESTO, TARIFA) DO NOTHING
                """,
                (id_factura, codigo, tarifa, base, valor),
            )
            return 0

    def insertar_pago_factura(
        self,
        conn: Connection,
        id_factura: int,
        datos_pago: dict,
    ) -> int:
        """Inserta los datos de pago de la factura."""

        codigo_forma = str(datos_pago.get('codigo_forma_pago') or '').strip()
        if not IdFormaPago.es_codigo_valido(codigo_forma):
            codigo_forma = IdFormaPago.contado  # Contado por defecto

        # Medio de pago: código DIAN directo
        codigo_medio = str(datos_pago.get('codigo_medio_pago') or '').strip() or None
        if codigo_medio and not IdMedioPago.es_codigo_valido(codigo_medio):
            logger.warning(
                'Código de medio de pago "%s" no reconocido, usando ZZZ (Otro).',
                codigo_medio,
            )
            codigo_medio = IdMedioPago.otro

        # Si es CONTADO, el medio de pago es obligatorio
        if codigo_forma == IdFormaPago.contado and not codigo_medio:
            codigo_medio = IdMedioPago.otro

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
                    ID_FACTURA, CODIGO_FORMA_PAGO, CODIGO_MEDIO_PAGO, PLAZO_EN_DIAS
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (ID_FACTURA) DO NOTHING
                """,
                (id_factura, codigo_forma, codigo_medio, plazo),
            )
            return id_factura

    def insertar_condicion_fiscal(
        self,
        conn: Connection,
        id_factura: int,
        id_tercero: int,
        tipo_tercero: str,
        responsabilidades: list,
    ) -> None:
        """Inserta las condiciones fiscales de un tercero en la factura."""

        with conn.cursor() as cur:
            for resp in responsabilidades:
                codigo = (resp.get('codigo') or '').strip()
                if not IdResponsabilidadFiscal.es_codigo_valido(codigo):
                    logger.debug(
                        'Código de responsabilidad fiscal "%s" no catalogado, omitiendo.',
                        codigo,
                    )
                    continue

                nota = (resp.get('descripcion') or '')[:300] or None
                if tipo_tercero:
                    prefijo = f'[{tipo_tercero} id={id_tercero}] '
                    nota = (prefijo + (nota or ''))[:300]

                cur.execute(
                    """
                    INSERT INTO FACTURACION.CONDICION_FISCAL_FACTURA (
                        ID_FACTURA, CODIGO_RESPONSABILIDAD, ES_APLICABLE, NOTAS_ADICIONALES
                    )
                    VALUES (%s, %s, TRUE, %s)
                    ON CONFLICT (ID_FACTURA, CODIGO_RESPONSABILIDAD) DO NOTHING
                    """,
                    (id_factura, codigo, nota),
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

    # ------------------------------------------------------------------
    # Operaciones de SOFTWARE
    # ------------------------------------------------------------------

    def insertar_fabricante_software(
        self,
        conn: Connection,
        numero_documento: str,
        razon_social: str,
    ) -> int:
        """Inserta o actualiza un fabricante de software."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.FABRICANTE_SOFTWARE (
                    NUMERO_DOCUMENTO, RAZON_SOCIAL
                )
                VALUES (%s, %s)
                ON CONFLICT (NUMERO_DOCUMENTO) DO UPDATE SET
                    RAZON_SOCIAL = EXCLUDED.RAZON_SOCIAL
                RETURNING ID_FABRICANTE_SOFTWARE
                """,
                (numero_documento, razon_social),
            )
            resultado = cur.fetchone()
            return resultado[0] if resultado else -1

    def insertar_producto_software(
        self,
        conn: Connection,
        id_fabricante: int,
        nombre_software: str,
    ) -> int:
        """Inserta o actualiza un producto de software."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.PRODUCTO_SOFTWARE (
                    ID_FABRICANTE_SOFTWARE, NOMBRE_SOFTWARE
                )
                VALUES (%s, %s)
                ON CONFLICT (ID_FABRICANTE_SOFTWARE, NOMBRE_SOFTWARE, COALESCE(VERSION_SOFTWARE, ''))
                DO UPDATE SET NOMBRE_SOFTWARE = EXCLUDED.NOMBRE_SOFTWARE
                RETURNING ID_PRODUCTO_SOFTWARE
                """,
                (id_fabricante, nombre_software),
            )
            resultado = cur.fetchone()
            return resultado[0] if resultado else -1

    def insertar_software_factura(
        self,
        conn: Connection,
        id_factura: int,
        id_producto: int,
        nit_proveedor_tecnologico: Optional[str] = None,
    ) -> None:
        """Asocia el software a la factura."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO FACTURACION.SOFTWARE_FACTURA (
                    ID_FACTURA, ID_PRODUCTO_SOFTWARE, NIT_PROVEEDOR_TECNOLOGICO
                )
                VALUES (%s, %s, %s)
                ON CONFLICT (ID_FACTURA) DO NOTHING
                """,
                (id_factura, id_producto, nit_proveedor_tecnologico),
            )

    # ------------------------------------------------------------------
    # Operaciones de EVENTO_DIAN_FACTURA
    # ------------------------------------------------------------------

    def insertar_evento_dian_factura(
        self,
        conn: Connection,
        id_factura: int,
        codigo_evento: str,
        descripcion: Optional[str] = None,
        id_rastreo: Optional[str] = None,
        fecha_evento: Optional[datetime] = None,
    ) -> int:
        """Inserta un evento DIAN asociado a una factura.

        Args:
            conn: Conexión activa.
            id_factura: ID de la factura.
            codigo_evento: Código del evento DIAN (FK a TIPO_EVENTO_DIAN).
            descripcion: Descripción textual del evento.
            id_rastreo: Número de rastreo del documento DIAN.
            fecha_evento: Fecha/hora del evento, si se conoce.

        Returns:
            ID del evento creado, o -1 si hubo error.
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO FACTURACION.EVENTO_DIAN_FACTURA (
                        ID_FACTURA, CODIGO_EVENTO, FECHA_EVENTO,
                        DESCRIPCION, ID_RASTREO
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING ID_EVENTO_FACTURA
                    """,
                    (
                        id_factura, codigo_evento, fecha_evento,
                        (descripcion or '')[:500] if descripcion else None,
                        id_rastreo,
                    ),
                )
                resultado = cur.fetchone()
                return resultado[0] if resultado else -1
        except Exception as err:
            logger.error(
                'Error al insertar EVENTO_DIAN_FACTURA (factura=%s, evento=%s): %s',
                id_factura, codigo_evento, err,
            )
            return -1
