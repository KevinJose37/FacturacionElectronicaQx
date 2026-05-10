"""Cache en memoria con TTL para endpoints de lectura frecuente.

Almacena resultados de queries costosas durante un período corto
para evitar roundtrips innecesarios a la BD remota.
El TTL por defecto se configura en ``config/settings.yaml``.
"""

import asyncio
import logging
import time

from config import load_yaml_config
from metadata.db_metadata import MensajesDB

logger = logging.getLogger(__name__)

_cache: dict = {}
_locks: dict = {}

_settings = load_yaml_config('settings.yaml')
DEFAULT_TTL = int(_settings.get('cache', {}).get('default_ttl_seconds', 30))


async def cached(key: str, fn, ttl: int = DEFAULT_TTL, *args, **kwargs):
    """Ejecuta fn() con cache basado en TTL.

    Si el resultado para ``key`` existe y no ha expirado, lo retorna
    sin ejecutar ``fn``. Usa locks para evitar stampede (múltiples
    requests recalculando el mismo cache simultáneamente).

    Args:
        key: Clave única del cache.
        fn: Función async a ejecutar si el cache está vacío/expirado.
        ttl: Tiempo de vida del cache en segundos.
        *args: Argumentos posicionales para fn.
        **kwargs: Argumentos clave para fn.

    Returns:
        Resultado de fn() (cacheado o fresco).
    """
    now = time.monotonic()
    resultado = None

    if key in _cache:
        expires_at, value = _cache[key]
        if now < expires_at:
            resultado = value

    if resultado is None:
        if key not in _locks:
            _locks[key] = asyncio.Lock()

        async with _locks[key]:
            if key in _cache:
                expires_at, value = _cache[key]
                if now < expires_at:
                    resultado = value

            if resultado is None:
                resultado = await fn(*args, **kwargs)
                _cache[key] = (now + ttl, resultado)
                logger.debug(MensajesDB.cache_set, key, ttl)

    return resultado


def invalidate(key: str | None = None) -> None:
    """Invalida una clave o todo el cache.

    Args:
        key: Clave a invalidar. Si es None, invalida todo.
    """
    if key is None:
        _cache.clear()
        logger.debug(MensajesDB.cache_cleared)
    elif key in _cache:
        del _cache[key]
        logger.debug(MensajesDB.cache_invalidated, key)
