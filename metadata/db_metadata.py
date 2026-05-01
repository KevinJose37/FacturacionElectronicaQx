"""Metadatos del módulo de base de datos.

Mensajes de error y textos del pool de conexiones y cache.
"""


class MensajesDB:
    """Mensajes de error y log del módulo de base de datos."""

    pool_no_inicializado = 'El pool de conexiones no ha sido inicializado. Llama a init_pool() primero.'
    """Error cuando se intenta obtener el pool antes de inicializarlo. Usado en connection.py."""

    pool_inicializado = 'Pool de conexiones async inicializado (%s:%s/%s)'
    """Mensaje de log al inicializar el pool. Usado en connection.py."""

    pool_cerrado = 'Pool de conexiones async cerrado.'
    """Mensaje de log al cerrar el pool. Usado en connection.py."""

    cache_set = 'Cache SET: %s (ttl=%ds)'
    """Mensaje de log al guardar una entrada en cache. Usado en cache.py."""

    cache_cleared = 'Cache CLEARED (all keys)'
    """Mensaje de log al limpiar todo el cache. Usado en cache.py."""

    cache_invalidated = 'Cache INVALIDATED: %s'
    """Mensaje de log al invalidar una clave específica. Usado en cache.py."""
