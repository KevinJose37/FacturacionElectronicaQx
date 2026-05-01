"""Script para poblar la BD con datos de prueba realistas."""

import psycopg
import uuid
import hashlib
import random
from datetime import datetime, timedelta, timezone

DB_CONFIG = {
    'host': '217.216.85.110',
    'port': 5433,
    'dbname': 'facturacion',
    'user': 'admin',
    'password': 'mysecretpassword',
}

PROVEEDORES = [
    ('900123456', '1', 'ACME COLOMBIA SAS', 'Acme Corp', 'acme@correo.com', '3001234567'),
    ('800987654', '3', 'GLOBEX INTERNACIONAL LTDA', 'Globex', 'globex@correo.com', '3009876543'),
    ('901112223', '4', 'INITECH SOLUCIONES SA', 'Initech', 'initech@correo.com', '3011112223'),
    ('902223334', '5', 'UMBRELLA SERVICIOS SAS', 'Umbrella', 'umbrella@correo.com', '3022223334'),
    ('903334445', '6', 'STARK INDUSTRIAS COLOMBIA', 'Stark Ind.', 'stark@correo.com', '3033334445'),
    ('904445556', '7', 'WAYNE ENTERPRISES CO', 'Wayne Ent.', 'wayne@correo.com', '3044445556'),
    ('905556667', '8', 'SOYLENT ALIMENTOS SAS', 'Soylent', 'soylent@correo.com', '3055556667'),
    ('906667778', '9', 'TYRELL TECHNOLOGIES SA', 'Tyrell', 'tyrell@correo.com', '3066667778'),
]

ADQUIRIENTE = ('860000000', '1', 'QUIPUX AI SAS', 'Quipux', 'facturacion@quipux.co', '3100000000')


def ejecutar_seed() -> None:
    """Ejecuta la inserción de datos seed en la BD."""
    conn = psycopg.connect(**DB_CONFIG)
    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            _limpiar_datos(cur)
            id_adquiriente = _insertar_adquiriente(cur)
            ids_emisores = _insertar_emisores(cur)
            ids_archivos = _insertar_archivos(cur, 80)
            ids_correos = _insertar_correos(cur, ids_archivos)
            ids_autorizaciones = _insertar_autorizaciones(cur, ids_emisores)
            ids_facturas = _insertar_facturas(
                cur, ids_emisores, id_adquiriente, ids_autorizaciones, ids_archivos
            )
            _insertar_detalles_facturas(cur, ids_facturas)
            _insertar_pagos(cur, ids_facturas)
            ids_procesos = _insertar_procesos_ingesta(cur, ids_correos, ids_archivos, ids_facturas)
            _insertar_validaciones_dian(cur, ids_facturas)
            _insertar_fabricantes_software(cur, ids_facturas)
            _insertar_eventos_ingesta(cur)
            _insertar_logs_heatmap(cur, ids_procesos)

        conn.commit()
        print('Seed completado exitosamente.')
    except Exception as e:
        conn.rollback()
        print(f'Error en seed: {e}')
        raise
    finally:
        conn.close()


def _limpiar_datos(cur) -> None:
    """Limpia tablas en orden de dependencias."""
    tablas = [
        'software_factura', 'producto_software', 'fabricante_software',
        'validacion_dian', 'impuesto_factura', 'impuesto_detalle_factura',
        'detalle_factura', 'pago_factura', 'condicion_fiscal_factura',
        'log_proceso', 'proceso_ingesta', 'evento_ingesta', 'escaneo_seguridad',
        'factura', 'autorizacion_numeracion_dian',
        'adjunto_correo', 'correo_entrante', 'archivo',
        'tercero',
    ]
    for t in tablas:
        cur.execute(f'DELETE FROM facturacion.{t}')
    print('Tablas limpiadas.')


def _insertar_adquiriente(cur) -> int:
    """Inserta el tercero adquiriente (Quipux)."""
    nit, dv, razon, comercial, correo, tel = ADQUIRIENTE
    cur.execute(
        'INSERT INTO facturacion.tercero '
        '(id_rol_tercero, numero_documento, digito_verificador, razon_social, '
        'nombre_comercial, correo_contacto, telefono_contacto) '
        'VALUES (2, %s, %s, %s, %s, %s, %s) RETURNING id_tercero',
        (nit, dv, razon, comercial, correo, tel),
    )
    id_tercero = cur.fetchone()[0]
    print(f'Adquiriente insertado: {razon} (id={id_tercero})')
    return id_tercero


def _insertar_emisores(cur) -> list:
    """Inserta los terceros emisores (proveedores)."""
    ids = []
    for nit, dv, razon, comercial, correo, tel in PROVEEDORES:
        cur.execute(
            'INSERT INTO facturacion.tercero '
            '(id_rol_tercero, numero_documento, digito_verificador, razon_social, '
            'nombre_comercial, correo_contacto, telefono_contacto) '
            'VALUES (1, %s, %s, %s, %s, %s, %s) RETURNING id_tercero',
            (nit, dv, razon, comercial, correo, tel),
        )
        ids.append(cur.fetchone()[0])
    print(f'{len(ids)} emisores insertados.')
    return ids


def _insertar_archivos(cur, cantidad: int) -> list:
    """Inserta registros de archivos ficticios."""
    ids = []
    for i in range(cantidad):
        sha = hashlib.sha256(f'archivo_seed_{i}_{uuid.uuid4()}'.encode()).hexdigest()
        cur.execute(
            'INSERT INTO facturacion.archivo '
            '(uri_almacenaje, nombre_original, tipo_mime, hash_sha256, tamano_bytes) '
            'VALUES (%s, %s, %s, %s, %s) RETURNING id_archivo',
            (
                f's3://facturacion-bucket/archivos/{sha[:16]}.xml',
                f'factura_{i:04d}.xml',
                'application/xml',
                sha,
                random.randint(5000, 150000),
            ),
        )
        ids.append(cur.fetchone()[0])
    print(f'{len(ids)} archivos insertados.')
    return ids


def _insertar_correos(cur, ids_archivos: list) -> list:
    """Inserta correos entrantes ficticios."""
    ids = []
    ahora = datetime.now(tz=timezone.utc)
    for i in range(min(30, len(ids_archivos))):
        fecha = ahora - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23))
        msg_id = f'<msg-{uuid.uuid4()}@gmail.com>'
        prov = PROVEEDORES[i % len(PROVEEDORES)]
        cur.execute(
            'INSERT INTO facturacion.correo_entrante '
            '(id_mensaje_email, remitente, destinatario, asunto, fecha_recepcion) '
            'VALUES (%s, %s, %s, %s, %s) RETURNING id_correo',
            (msg_id, prov[4], 'facturacion@quipux.co',
             f'{prov[0]};{prov[2]};FE-{i:04d};01;{prov[3]}', fecha),
        )
        ids.append(cur.fetchone()[0])
    print(f'{len(ids)} correos insertados.')
    return ids


def _insertar_autorizaciones(cur, ids_emisores: list) -> dict:
    """Inserta autorizaciones de numeración DIAN."""
    resultado = {}
    for idx, id_emisor in enumerate(ids_emisores):
        cur.execute(
            'INSERT INTO facturacion.autorizacion_numeracion_dian '
            '(id_tercero_emisor, prefijo_facturacion, numero_resolucion, '
            'rango_desde, rango_hasta, fecha_autorizacion, '
            'fecha_inicio_vigencia, fecha_fin_vigencia) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_autorizacion',
            (
                id_emisor, f'FE{idx}', f'RES-{18760000 + idx}',
                1, 50000,
                '2025-01-15', '2025-01-15', '2027-01-15',
            ),
        )
        resultado[id_emisor] = cur.fetchone()[0]
    print(f'{len(resultado)} autorizaciones insertadas.')
    return resultado


def _insertar_facturas(cur, ids_emisores, id_adquiriente, autorizaciones, ids_archivos) -> list:
    """Inserta facturas con estados variados y tipos de documento."""
    ids = []
    ahora = datetime.now(tz=timezone.utc)
    estados = [7, 7, 7, 7, 6, 8, 10, 7, 9, 7]  # VALIDADO_DIAN, FACTURA_PARSED, RECHAZADO, ERROR, PERSISTIDO
    tipos_doc = ['FE', 'FE', 'FE', 'FE', 'FE', 'NC', 'NC', 'ND', 'DS', 'FE']  # Distribución realista

    for i in range(min(40, len(ids_archivos) - 10)):
        id_emisor = ids_emisores[i % len(ids_emisores)]
        id_aut = autorizaciones[id_emisor]
        id_archivo_xml = ids_archivos[i]
        estado = estados[i % len(estados)]
        tipo_doc = tipos_doc[i % len(tipos_doc)]
        fecha_gen = ahora - timedelta(days=random.randint(0, 14), hours=random.randint(0, 12))
        monto = round(random.uniform(50000, 5000000), 2)
        cufe = hashlib.sha256(f'cufe_{i}_{uuid.uuid4()}'.encode()).hexdigest()[:96]

        cur.execute(
            'INSERT INTO facturacion.factura '
            '(cufe, prefijo_facturacion, numero_factura, id_tercero_emisor, '
            'id_tercero_adquiriente, id_autorizacion, fecha_generacion, '
            'fecha_expedicion, codigo_moneda, valor_total, '
            'id_archivo_xml_origen, id_estado_proceso, tipo_documento) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) '
            'RETURNING id_factura',
            (
                cufe, f'FE{i % len(ids_emisores)}', f'{1000 + i}',
                id_emisor, id_adquiriente, id_aut,
                fecha_gen, fecha_gen, 'COP', monto,
                id_archivo_xml, estado, tipo_doc,
            ),
        )
        ids.append(cur.fetchone()[0])
    print(f'{len(ids)} facturas insertadas (con tipo_documento variado).')
    return ids


def _insertar_detalles_facturas(cur, ids_facturas: list) -> None:
    """Inserta líneas de detalle para cada factura."""
    total = 0
    for id_factura in ids_facturas:
        num_lineas = random.randint(1, 5)
        for linea in range(1, num_lineas + 1):
            cantidad = round(random.uniform(1, 100), 2)
            valor_unit = round(random.uniform(1000, 50000), 2)
            valor_total = round(cantidad * valor_unit, 2)
            cur.execute(
                'INSERT INTO facturacion.detalle_factura '
                '(id_factura, numero_linea, descripcion_item, cantidad, '
                'valor_unitario, valor_total_linea) '
                'VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_detalle',
                (
                    id_factura, linea,
                    f'Producto/Servicio {random.choice(["A","B","C","D"])}-{linea:03d}',
                    cantidad, valor_unit, valor_total,
                ),
            )
            id_detalle = cur.fetchone()[0]
            tarifa = random.choice([0.19, 0.05, 0.0])
            if tarifa > 0:
                cur.execute(
                    'INSERT INTO facturacion.impuesto_detalle_factura '
                    '(id_detalle, id_impuesto, tarifa, base_gravable, valor_impuesto) '
                    'VALUES (%s, 1, %s, %s, %s)',
                    (id_detalle, tarifa, valor_total, round(valor_total * tarifa, 2)),
                )
            total += 1
    print(f'{total} detalles de factura insertados.')


def _insertar_pagos(cur, ids_facturas: list) -> None:
    """Inserta información de pago para cada factura."""
    for id_factura in ids_facturas:
        forma = random.choice([1, 2])
        medio = random.choice([1, 2, 3, 4]) if forma == 1 else None
        plazo = None if forma == 1 else random.choice([30, 60, 90])
        cur.execute(
            'INSERT INTO facturacion.pago_factura '
            '(id_factura, id_forma_pago, id_medio_pago, plazo_en_dias) '
            'VALUES (%s, %s, %s, %s)',
            (id_factura, forma, medio, plazo),
        )
    print(f'{len(ids_facturas)} pagos insertados.')


def _insertar_procesos_ingesta(cur, ids_correos, ids_archivos, ids_facturas) -> None:
    """Inserta procesos de ingesta con logs."""
    ahora = datetime.now(tz=timezone.utc)
    etapas = [
        ('RECEPCION', 1), ('VERIFICACION_ADJUNTO', 2), ('ESCANEO', 3),
        ('EXTRACCION_XML', 5), ('PARSEO', 6), ('VALIDACION_DIAN', 7), ('PERSISTENCIA', 9),
    ]
    niveles_log = ['info', 'info', 'info', 'info', 'info', 'warn', 'error']
    fuentes = ['pipeline', 'ocr', 'validator', 'erp', 'queue', 'ai', 'auth', 'scheduler']

    total_logs = 0
    ids_procesos = []
    for i in range(min(len(ids_correos), len(ids_facturas), 25)):
        id_correo = ids_correos[i % len(ids_correos)]
        estado_final = random.choice([7, 8, 9, 10])
        clave = hashlib.sha256(f'idem_{i}_{uuid.uuid4()}'.encode()).hexdigest()
        cufe = hashlib.sha256(f'cufe_proc_{i}'.encode()).hexdigest()[:96]
        fecha_inicio = ahora - timedelta(days=random.randint(0, 14), minutes=random.randint(0, 1440))

        # Dejar algunos procesos sin fecha_fin para probar 'atascadas'
        fecha_fin = None
        if i < 22:  # 22 de 25 con fecha_fin
            fecha_fin = fecha_inicio + timedelta(seconds=random.uniform(0.5, 5.0))

        cur.execute(
            'INSERT INTO facturacion.proceso_ingesta '
            '(id_correo, id_archivo_origen, clave_idempotencia, version_motor, '
            'id_estado_proceso, cufe_detectado, fecha_inicio, fecha_fin) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id_proceso',
            (
                id_correo, ids_archivos[i % len(ids_archivos)],
                clave, 'v1.0.0', estado_final, cufe,
                fecha_inicio, fecha_fin,
            ),
        )
        id_proceso = cur.fetchone()[0]
        ids_procesos.append(id_proceso)

        num_etapas = random.randint(3, len(etapas))
        for seq, (codigo_etapa, id_estado) in enumerate(etapas[:num_etapas], 1):
            nivel = random.choice(niveles_log)
            fuente = random.choice(fuentes)
            fecha_log = fecha_inicio + timedelta(seconds=seq * random.uniform(0.1, 1.0))
            detalle_error = None
            if nivel == 'error':
                detalle_error = random.choice([
                    'CUFE no coincide con el esperado',
                    'Timeout en servicio DIAN (8s)',
                    'NIT del emisor no registrado en DIAN',
                    'XML mal formado: tag InvoiceLine sin cerrar',
                    'Archivo ZIP corrupto o vacío',
                ])
            cur.execute(
                'INSERT INTO facturacion.log_proceso '
                '(id_proceso, numero_secuencia, codigo_etapa, id_estado_proceso, '
                'fecha_inicio, fecha_fin, detalle_json, detalle_error) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (
                    id_proceso, seq, codigo_etapa, id_estado,
                    fecha_log, fecha_log + timedelta(seconds=random.uniform(0.05, 0.5)),
                    f'{{"fuente": "{fuente}", "nivel": "{nivel}"}}',
                    detalle_error,
                ),
            )
            total_logs += 1

    print(f'{min(len(ids_correos), 25)} procesos y {total_logs} logs insertados.')
    return ids_procesos


def _insertar_validaciones_dian(cur, ids_facturas: list) -> None:
    """Inserta validaciones DIAN para facturas."""
    total = 0
    for id_factura in ids_facturas:
        estado = random.choice([7, 7, 7, 8])
        codigo_resp = 'OK' if estado == 7 else random.choice(['REJECT-01', 'REJECT-02', 'REJECT-03'])
        desc_resp = (
            'Documento validado correctamente' if estado == 7
            else random.choice([
                'CUFE duplicado en sistema DIAN',
                'Resolución de facturación vencida',
                'NIT del emisor no habilitado',
            ])
        )
        cur.execute(
            'INSERT INTO facturacion.validacion_dian '
            '(id_factura, fecha_validacion, codigo_respuesta, '
            'descripcion_respuesta, id_estado_proceso) '
            'VALUES (%s, NOW(), %s, %s, %s)',
            (id_factura, codigo_resp, desc_resp, estado),
        )
        total += 1
    print(f'{total} validaciones DIAN insertadas.')


def _insertar_fabricantes_software(cur, ids_facturas: list) -> None:
    """Inserta fabricantes y productos de software."""
    fabricantes = [
        ('900999001', 'FacturaTech SAS'),
        ('900999002', 'ColFactura SA'),
    ]
    ids_fab = []
    for nit, razon in fabricantes:
        cur.execute(
            'INSERT INTO facturacion.fabricante_software '
            '(numero_documento, razon_social) '
            'VALUES (%s, %s) RETURNING id_fabricante_software',
            (nit, razon),
        )
        ids_fab.append(cur.fetchone()[0])

    ids_prod = []
    for idx, id_fab in enumerate(ids_fab):
        cur.execute(
            'INSERT INTO facturacion.producto_software '
            '(id_fabricante_software, nombre_software, version_software) '
            'VALUES (%s, %s, %s) RETURNING id_producto_software',
            (id_fab, f'FacturaElectronica Pro v{idx + 1}', f'{idx + 3}.0.1'),
        )
        ids_prod.append(cur.fetchone()[0])

    for id_factura in ids_facturas[:20]:
        cur.execute(
            'INSERT INTO facturacion.software_factura '
            '(id_factura, id_producto_software) '
            'VALUES (%s, %s)',
            (id_factura, random.choice(ids_prod)),
        )
    print(f'{len(fabricantes)} fabricantes, {len(ids_prod)} productos de software insertados.')


def _insertar_eventos_ingesta(cur) -> None:
    """Inserta eventos de ingesta con diferentes estados para la cola."""
    ahora = datetime.now(tz=timezone.utc)
    estados = ['PENDIENTE', 'PENDIENTE', 'PENDIENTE', 'PROCESADO', 'PROCESADO', 'ERROR']
    total = 0
    for i in range(18):
        estado = estados[i % len(estados)]
        cur.execute(
            'INSERT INTO facturacion.evento_ingesta '
            '(id_evento, estado, origen, datos_json, intentos) '
            'VALUES (%s, %s, %s, %s, %s)',
            (
                str(uuid.uuid4()),
                estado,
                'email_listener',
                f'{{"correo_id": {i + 1}, "asunto": "FE-{i:04d}"}}',
                random.randint(0, 3) if estado == 'ERROR' else 0,
            ),
        )
        total += 1
    print(f'{total} eventos de ingesta insertados ({sum(1 for s in estados if s == "PENDIENTE") * 3} pendientes).')


def _insertar_logs_heatmap(cur, ids_procesos: list) -> None:
    """Inserta logs adicionales distribuidos por hora/día para poblar el heatmap.

    Genera errores en diferentes horas del día y días de la semana
    para que el heatmap tenga datos variados.
    """
    ahora = datetime.now(tz=timezone.utc)
    errores_heatmap = [
        'CUFE no coincide con el esperado',
        'Timeout en servicio DIAN (8s)',
        'NIT del emisor no registrado en DIAN',
        'XML mal formado: tag InvoiceLine sin cerrar',
        'Error de conexión con servicio externo',
        'Certificado de firma vencido',
        'Formato de moneda inválido',
    ]
    total = 0
    for dia_offset in range(7):  # Últimos 7 días
        # Más errores en horario laboral (9-18), menos fuera
        horas_con_errores = list(range(7, 22))  # 7am a 10pm
        for hora in horas_con_errores:
            num_errores = random.randint(0, 3) if 9 <= hora <= 18 else random.randint(0, 1)
            for _ in range(num_errores):
                id_proceso = random.choice(ids_procesos)
                fecha_log = (ahora - timedelta(days=dia_offset)).replace(
                    hour=hora, minute=random.randint(0, 59), second=random.randint(0, 59)
                )
                # Obtener siguiente secuencia
                cur.execute(
                    'SELECT COALESCE(MAX(numero_secuencia), 0) + 1 '
                    'FROM facturacion.log_proceso WHERE id_proceso = %s',
                    (id_proceso,),
                )
                seq = cur.fetchone()[0]
                cur.execute(
                    'INSERT INTO facturacion.log_proceso '
                    '(id_proceso, numero_secuencia, codigo_etapa, id_estado_proceso, '
                    'fecha_inicio, fecha_fin, detalle_json, detalle_error) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                    (
                        id_proceso, seq,
                        random.choice(['VALIDACION_DIAN', 'ESCANEO', 'PARSEO']),
                        random.choice([8, 10]),
                        fecha_log,
                        fecha_log + timedelta(seconds=random.uniform(0.1, 2.0)),
                        '{"fuente": "pipeline", "nivel": "error"}',
                        random.choice(errores_heatmap),
                    ),
                )
                total += 1
    print(f'{total} logs adicionales para heatmap insertados.')


if __name__ == '__main__':
    ejecutar_seed()
