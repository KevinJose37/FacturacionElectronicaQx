import os
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=128)
def get_env_var(key: str, default: Any = None) -> Any:
    """Obtiene una variable de entorno de forma cacheada.

    Usa lru_cache para evitar múltiples lecturas al SO y mantener pureza.

    Args:
        key: Clave de la variable de entorno a buscar.
        default: Valor por defecto si no se encuentra la clave.

    Returns:
        El valor de la variable de entorno o el valor por defecto.
    """
    valor_entorno = os.environ.get(key, default)
    return valor_entorno


def get_config(key: str, default: Any = None) -> Any:
    """Obtiene el valor de una configuración del sistema.

    Función de orden superior que puede extenderse para leer de
    un dict, un archivo .env o un secret manager.

    Args:
        key: Clave de la configuración a buscar.
        default: Valor por defecto si no se encuentra la clave.

    Returns:
        El valor de la configuración o el valor por defecto.
    """
    valor_configuracion = get_env_var(key, default)
    return valor_configuracion


@lru_cache(maxsize=1)
def get_postgres_config() -> dict:
    """Devuelve la configuración de conexión para PostgreSQL.

    Retorna un diccionario como estructura de datos inmutable y pura.

    Returns:
        Diccionario con la configuración de la base de datos PostgreSQL.
    """
    configuracion = {
        'host': get_config('DB_HOST', 'localhost'),
        'port': get_config('DB_PORT', '5432'),
        'dbname': get_config('DB_NAME', 'postgres'),
        'user': get_config('DB_USER', 'postgres'),
        'password': get_config('DB_PASSWORD', 'postgres')
    }
    return configuracion


def create_postgres_connection(config: dict) -> Any:
    """Crea y retorna una conexión a PostgreSQL.

    Función pura que recibe configuración y retorna una conexión,
    separando el manejo de estado de la lectura de variables.

    Args:
        config: Diccionario con los parámetros de conexión.

    Returns:
        Conexión activa a PostgreSQL.
    """
    import psycopg2
    conexion = psycopg2.connect(**config)
    return conexion
