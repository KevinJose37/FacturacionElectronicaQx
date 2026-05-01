"""Paquete de base de datos y cache.

Centraliza el pool de conexiones async y el sistema de cache en memoria.
"""

from core.python.db.connection import get_pool, init_pool, close_pool
from core.python.db.cache import cached, invalidate, DEFAULT_TTL

__all__ = [
    'get_pool',
    'init_pool',
    'close_pool',
    'cached',
    'invalidate',
    'DEFAULT_TTL',
]
