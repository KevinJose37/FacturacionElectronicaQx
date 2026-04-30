"""Pool de conexiones asíncrono para PostgreSQL.

Provee un AsyncConnectionPool gestionado por el lifespan de FastAPI.
"""

import logging
import os

from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    """Inicializa el pool de conexiones asíncrono.

    Lee la configuración de variables de entorno y crea el pool.

    Raises:
        RuntimeError: Si las variables de entorno requeridas no están definidas.
    """
    global _pool

    host = os.environ.get('DB_HOST', os.environ.get('POSTGRES_HOST', 'localhost'))
    port = os.environ.get('DB_PORT', os.environ.get('POSTGRES_PORT', '5432'))
    dbname = os.environ.get('DB_NAME', os.environ.get('POSTGRES_DB', 'facturacion'))
    user = os.environ.get('DB_USER', os.environ.get('POSTGRES_USER', 'admin'))
    password = os.environ.get('DB_PASSWORD', os.environ.get('POSTGRES_PASSWORD', ''))

    conninfo = f'host={host} port={port} dbname={dbname} user={user} password={password}'

    _pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=2,
        max_size=10,
        open=False,
    )
    await _pool.open()
    logger.info('Pool de conexiones async inicializado (%s:%s/%s)', host, port, dbname)


async def close_pool() -> None:
    """Cierra el pool de conexiones de forma limpia."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info('Pool de conexiones async cerrado.')


def get_pool() -> AsyncConnectionPool:
    """Retorna el pool de conexiones activo.

    Returns:
        Pool de conexiones asíncrono.

    Raises:
        RuntimeError: Si el pool no ha sido inicializado.
    """
    if _pool is None:
        raise RuntimeError('El pool de conexiones no ha sido inicializado. Llama a init_pool() primero.')
    return _pool
