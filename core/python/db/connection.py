"""Pool de conexiones asíncrono para PostgreSQL.

Provee un AsyncConnectionPool gestionado por el lifespan de FastAPI.
Los parámetros de conexión se leen de ``config.get_postgres_config()``
y los tamaños del pool desde ``config/settings.yaml``.
"""

import logging

from psycopg_pool import AsyncConnectionPool

from config import get_postgres_config, load_yaml_config
from metadata.db_metadata import MensajesDB

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None
_settings = load_yaml_config('settings.yaml')
_pool_cfg = _settings.get('database', {}).get('pool', {})


async def init_pool() -> None:
    """Inicializa el pool de conexiones asíncrono.

    Lee la configuración de ``get_postgres_config()`` y crea el pool
    con los tamaños definidos en ``config/settings.yaml``.

    Raises:
        RuntimeError: Si las variables de entorno requeridas no están definidas.
    """
    global _pool

    db_config = get_postgres_config()
    host = db_config['host']
    port = db_config['port']
    dbname = db_config['dbname']
    user = db_config['user']
    password = db_config['password']

    conninfo = f'host={host} port={port} dbname={dbname} user={user} password={password}'
    min_size = int(_pool_cfg.get('min_size', 5))
    max_size = int(_pool_cfg.get('max_size', 15))

    _pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=min_size,
        max_size=max_size,
        open=False,
    )
    await _pool.open()
    logger.info(MensajesDB.pool_inicializado, host, port, dbname)

    try:
        async with _pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "ALTER TABLE facturacion.factura ADD COLUMN IF NOT EXISTS verificacion_grafica_estado VARCHAR(20) DEFAULT NULL;"
                )
                await cur.execute(
                    "ALTER TABLE facturacion.factura ADD COLUMN IF NOT EXISTS motivo_rechazo TEXT DEFAULT NULL;"
                )
                await cur.execute(
                    "ALTER TABLE facturacion.factura ADD COLUMN IF NOT EXISTS verificacion_grafica_detalle JSONB DEFAULT NULL;"
                )
                logger.info("Migracion: Columnas de verificacion grafica y motivos de rechazo verificadas/creadas exitosamente.")
    except Exception as e:
        logger.error(f"Error al ejecutar migraciones de columnas en factura: {e}")


async def close_pool() -> None:
    """Cierra el pool de conexiones de forma limpia."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info(MensajesDB.pool_cerrado)


def get_pool() -> AsyncConnectionPool:
    """Retorna el pool de conexiones activo.

    Raises:
        RuntimeError: Si el pool no ha sido inicializado.
    """
    if _pool is None:
        raise RuntimeError(MensajesDB.pool_no_inicializado)
    resultado = _pool
    return resultado
