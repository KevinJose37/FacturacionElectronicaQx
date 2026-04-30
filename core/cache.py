"""Cache en memoria con TTL para endpoints de lectura frecuente.

Almacena resultados de queries costosas durante un período corto
para evitar roundtrips innecesarios a la BD remota.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, Any]] = {}
_locks: dict[str, asyncio.Lock] = {}

# TTL por defecto en segundos (30s es razonable para un dashboard)
DEFAULT_TTL = 30


async def cached(
    key: str,
    fn: Callable[..., Coroutine],
    ttl: int = DEFAULT_TTL,
    *args,
    **kwargs,
) -> Any:
    """Ejecuta fn() con cache basado en TTL.

    Si el resultado para `key` existe y no ha expirado, lo retorna
    sin ejecutar `fn`. Usa locks para evitar stampede (múltiples
    requests recalculando el mismo cache simultáneamente).

    Args:
        key: Clave única del cache.
        fn: Función async a ejecutar si el cache está vacío/expirado.
        ttl: Tiempo de vida del cache en segundos.
        *args: Argumentos para fn.
        **kwargs: Argumentos clave para fn.

    Returns:
        Resultado de fn() (cacheado o fresco).
    """
    now = time.monotonic()

    # Fast path: cache hit
    if key in _cache:
        expires_at, value = _cache[key]
        if now < expires_at:
            return value

    # Obtener o crear lock para esta key
    if key not in _locks:
        _locks[key] = asyncio.Lock()

    async with _locks[key]:
        # Double-check después del lock (otro request pudo llenar el cache)
        if key in _cache:
            expires_at, value = _cache[key]
            if now < expires_at:
                return value

        # Cache miss: ejecutar la función
        result = await fn(*args, **kwargs)
        _cache[key] = (now + ttl, result)
        logger.debug('Cache SET: %s (ttl=%ds)', key, ttl)
        return result


def invalidate(key: str | None = None) -> None:
    """Invalida una clave o todo el cache.

    Args:
        key: Clave a invalidar. Si es None, invalida todo.
    """
    if key is None:
        _cache.clear()
        logger.debug('Cache CLEARED (all keys)')
    elif key in _cache:
        del _cache[key]
        logger.debug('Cache INVALIDATED: %s', key)
