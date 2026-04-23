import logging
from typing import Any

import psycopg2
from psycopg2 import sql
import psycopg2.extras

from config import create_postgres_connection, get_postgres_config

logger = logging.getLogger(__name__)


def obtener_conexion() -> Any:
    """Obtiene una conexión activa a la base de datos PostgreSQL.

    Returns:
        Conexión activa a PostgreSQL.
    """
    configuracion = get_postgres_config()
    conexion = create_postgres_connection(configuracion)
    return conexion


def insertar_datos(conexion: Any, esquema: str, tabla: str, datos: dict) -> Any:
    """Inserta datos en una tabla específica y retorna el ID generado.

    Función pura respecto a la conexión (la recibe por inyección).

    Args:
        conexion: Conexión activa a PostgreSQL.
        esquema: Nombre del esquema en la base de datos.
        tabla: Nombre de la tabla donde se insertarán los datos.
        datos: Diccionario con los nombres de las columnas y sus valores.

    Returns:
        El ID del registro insertado, o None si no hubo retorno.

    Raises:
        Exception: Si ocurre un error al ejecutar la consulta SQL.
    """
    columnas = list(datos.keys())
    valores = [datos[col] for col in columnas]

    query = sql.SQL('INSERT INTO {esquema}.{tabla} ({campos}) VALUES ({valores_placeholder}) RETURNING *').format(
        esquema=sql.Identifier(esquema),
        tabla=sql.Identifier(tabla),
        campos=sql.SQL(', ').join(map(sql.Identifier, columnas)),
        valores_placeholder=sql.SQL(', ').join([sql.Placeholder()] * len(valores))
    )

    id_insertado = None

    try:
        with conexion.cursor() as cursor:
            cursor.execute(query, valores)
            resultado = cursor.fetchone()
            conexion.commit()

            if resultado:
                id_insertado = resultado[0]
    except Exception as e:
        conexion.rollback()
        logger.error(f'Error insertando datos en {esquema}.{tabla}: {e}')
        raise

    return id_insertado


def ejecutar_consulta(conexion: Any, query_str: str, params: tuple | None = None) -> list:
    """Ejecuta una consulta general de lectura en la base de datos.

    Args:
        conexion: Conexión activa a PostgreSQL.
        query_str: Consulta SQL a ejecutar.
        params: Tupla de parámetros para la consulta, opcional.

    Returns:
        Lista de diccionarios con los resultados de la consulta.

    Raises:
        Exception: Si ocurre un error al ejecutar la consulta.
    """
    resultados_finales = []

    try:
        with conexion.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(query_str, params)
            if cursor.description:
                resultados_finales = list(cursor.fetchall())
    except Exception as e:
        logger.error(f'Error ejecutando consulta: {e}')
        raise

    return resultados_finales


def actualizar_datos(conexion: Any, esquema: str, tabla: str, datos: dict, condicion: dict) -> None:
    """Actualiza datos en una tabla bajo condiciones específicas.

    Args:
        conexion: Conexión activa a PostgreSQL.
        esquema: Nombre del esquema en la base de datos.
        tabla: Nombre de la tabla a actualizar.
        datos: Diccionario con los campos y valores nuevos.
        condicion: Diccionario con los campos y valores de la condición.

    Raises:
        Exception: Si ocurre un error al ejecutar la actualización.
    """
    partes_set = [sql.SQL('{} = {}').format(sql.Identifier(k), sql.Placeholder()) for k in datos.keys()]
    partes_where = [sql.SQL('{} = {}').format(sql.Identifier(k), sql.Placeholder()) for k in condicion.keys()]

    query = sql.SQL('UPDATE {esquema}.{tabla} SET {set_expr} WHERE {where_expr}').format(
        esquema=sql.Identifier(esquema),
        tabla=sql.Identifier(tabla),
        set_expr=sql.SQL(', ').join(partes_set),
        where_expr=sql.SQL(' AND ').join(partes_where)
    )

    valores = list(datos.values()) + list(condicion.values())

    try:
        with conexion.cursor() as cursor:
            cursor.execute(query, valores)
            conexion.commit()
    except Exception as e:
        conexion.rollback()
        logger.error(f'Error actualizando datos en {esquema}.{tabla}: {e}')
        raise
