"""Migración: Limpieza total de datos.

Trunca todas las tablas transaccionales conservando los catálogos (TIPO_*).
Los catálogos contienen datos de referencia inmutables que el sistema necesita
para funcionar (estados, formas de pago, tipos de impuesto, etc.).

Uso:
    python scripts/truncate_all.py
"""

import psycopg

DB_CONFIG = {
    'host': '217.216.85.110',
    'port': 5433,
    'dbname': 'facturacion',
    'user': 'admin',
    'password': 'mysecretpassword',
}

# Orden de truncado: hijos primero (respeta foreign keys con CASCADE)
TABLAS_A_LIMPIAR = [
    'FACTURACION.SOFTWARE_FACTURA',
    'FACTURACION.PRODUCTO_SOFTWARE',
    'FACTURACION.FABRICANTE_SOFTWARE',
    'FACTURACION.VALIDACION_DIAN',
    'FACTURACION.IMPUESTO_DETALLE_FACTURA',
    'FACTURACION.IMPUESTO_FACTURA',
    'FACTURACION.DETALLE_FACTURA',
    'FACTURACION.PAGO_FACTURA',
    'FACTURACION.CONDICION_FISCAL_FACTURA',
    'FACTURACION.FACTURA',
    'FACTURACION.AUTORIZACION_NUMERACION_DIAN',
    'FACTURACION.TERCERO',
    'FACTURACION.PROCESO_INGESTA',
    'FACTURACION.EVENTO_INGESTA',
    'FACTURACION.ADJUNTOS_CORREO',
    'FACTURACION.CORREO_ENTRANTE',
]


def ejecutar_truncado() -> None:
    """Trunca todas las tablas transaccionales con CASCADE."""
    conn = psycopg.connect(**DB_CONFIG)
    conn.autocommit = False

    try:
        cur = conn.cursor()

        tablas_str = ', '.join(TABLAS_A_LIMPIAR)
        cur.execute(f'TRUNCATE TABLE {tablas_str} RESTART IDENTITY CASCADE')

        conn.commit()
        print(f'OK: {len(TABLAS_A_LIMPIAR)} tablas limpiadas exitosamente.')
        print('   Catalogos (TIPO_*) conservados.')

    except Exception as e:
        conn.rollback()
        print(f'ERROR durante el truncado: {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    confirmacion = input(
        'ADVERTENCIA: Esto eliminara TODOS los datos transaccionales.\n'
        'Los catalogos (TIPO_*) se conservan.\n'
        'Continuar? (escribir SI para confirmar): '
    )
    if confirmacion.strip().upper() == 'SI':
        ejecutar_truncado()
    else:
        print('Operacion cancelada.')
