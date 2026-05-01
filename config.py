"""Configuración global del sistema. Centraliza variables de entorno,
parámetros de PostgreSQL y credenciales de S3."""

import os
import yaml

from pathlib import Path
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
        'host': get_config('POSTGRES_HOST', 'localhost'),
        'port': get_config('POSTGRES_PORT', '5432'),
        'dbname': get_config('POSTGRES_DB', 'postgres'),
        'user': get_config('POSTGRES_USER', 'postgres'),
        'password': get_config('POSTGRES_PASSWORD', 'postgres')
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


@lru_cache(maxsize=1)
def get_aws_config() -> dict:
    """Lee la configuración de AWS desde el archivo YAML de credenciales.

    Busca en 'input/credentials/s3_connection.yml'.

    Returns:
        Diccionario con las credenciales (access_key, secret_key, bucket_name).
    """
    ruta_yml = Path("input/credentials/s3_connection.yml")
    config_yaml = {}

    if ruta_yml.exists():
        try:
            with open(ruta_yml, 'r', encoding='utf-8') as f:
                config_yaml = yaml.safe_load(f) or {}
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Error leyendo {ruta_yml}: {e}")

    return {
        'access_key': config_yaml.get('access_key'),
        'secret_key': config_yaml.get('secret_key'),
        'bucket_name': config_yaml.get('bucket_s3', 'facturacion-electronica-temporal')
    }


def load_yaml_config(file_name: str) -> dict:
    """Carga un archivo YAML de la carpeta config.

    Args:
        file_name: Nombre del archivo .yml o .yaml.

    Returns:
        Diccionario con la configuración cargada.
    """
    import yaml

    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, 'config', file_name)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        return config_data or {}
    except Exception:
        return {}



def get_tool_definitions() -> list:
    """Obtiene las definiciones de tools del LLM desde el archivo YAML.

    Carga las definiciones de function calling (OpenAI format) desde
    ``config/tool_definitions.yml``.

    Returns:
        Lista de diccionarios con las definiciones de cada tool.
    """
    data = load_yaml_config('tool_definitions.yml')
    resultado = data.get('tools', [])
    return resultado


def load_yaml_queries(ruta_relativa: str) -> dict:
    """Carga un archivo YAML de queries desde la carpeta input/queries.

    Args:
        ruta_relativa:
            Ruta relativa dentro de input/queries (ej: 'chat/queries_chat.yml').

    Returns:
        Diccionario con las queries cargadas.
    """
    import yaml

    base_path = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_path, 'input', 'queries', ruta_relativa)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            queries_data = yaml.safe_load(f)
        resultado = queries_data or {}
    except Exception:
        resultado = {}
    return resultado


def get_queries_chat() -> dict:
    """Obtiene las consultas SQL del chatbot desde el archivo YAML.

    Carga queries desde ``input/queries/chat/queries_chat.yml``.

    Returns:
        Diccionario con las queries SQL y fragmentos de filtros.
    """
    queries = load_yaml_queries('chat/queries_chat.yml')
    return queries


def get_queries_services() -> dict:
    """Obtiene las consultas SQL de los servicios del frontend.

    Carga queries desde ``input/queries/services/queries_services.yml``.

    Returns:
        Diccionario con las queries SQL organizadas por servicio.
    """
    queries = load_yaml_queries('services/queries_services.yml')
    return queries
