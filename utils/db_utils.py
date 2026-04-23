import os
import logging
import psycopg2
import psycopg2.extras
from psycopg2 import sql
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Clase general para gestionar la conexión y operaciones con la base de datos PostgreSQL."""

    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = os.getenv("DB_PORT", "5432")
        self.dbname = os.getenv("DB_NAME", "postgres")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "postgres")
        self.connection = None

    def connect(self):
        """Establece la conexión con la base de datos."""
        if not self.connection or self.connection.closed:
            try:
                self.connection = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    dbname=self.dbname,
                    user=self.user,
                    password=self.password
                )
                self.connection.autocommit = True
            except Exception as e:
                logger.error(f"Error conectando a la base de datos: {e}")
                raise

    def disconnect(self):
        """Cierra la conexión con la base de datos."""
        if self.connection and not self.connection.closed:
            self.connection.close()

    def insert_data(self, schema: str, table: str, data: Dict[str, Any]) -> Optional[Any]:
        """
        Inserta datos en cualquier tabla.
        
        Args:
            schema: Nombre del esquema.
            table: Nombre de la tabla.
            data: Diccionario con los nombres de las columnas y sus valores.
            
        Returns:
            El ID del registro insertado si la tabla tiene una llave primaria serial/identity.
        """
        self.connect()
        if not self.connection:
            raise Exception("No se pudo establecer la conexión a la base de datos.")
            
        columns = list(data.keys())
        values = [data[column] for column in columns]
        
        query = sql.SQL("INSERT INTO {schema}.{table} ({fields}) VALUES ({values}) RETURNING *").format(
            schema=sql.Identifier(schema),
            table=sql.Identifier(table),
            fields=sql.SQL(', ').join(map(sql.Identifier, columns)),
            values=sql.SQL(', ').join([sql.Placeholder()] * len(values))
        )
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, values)
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error insertando datos en {schema}.{table}: {e}")
            raise

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Any]:
        """
        Ejecuta una consulta general y devuelve los resultados como una lista de diccionarios.
        """
        self.connect()
        if not self.connection:
            raise Exception("No se pudo establecer la conexión a la base de datos.")
            
        try:
            with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description:
                    return list(cursor.fetchall())
                return []
        except Exception as e:
            logger.error(f"Error ejecutando consulta: {e}")
            raise

    def update_data(self, schema: str, table: str, data: Dict[str, Any], condition: Dict[str, Any]) -> None:
        """
        Actualiza datos en cualquier tabla bajo una condición.
        """
        self.connect()
        if not self.connection:
            raise Exception("No se pudo establecer la conexión a la base de datos.")
        
        set_parts = [sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder()) for k in data.keys()]
        where_parts = [sql.SQL("{} = {}").format(sql.Identifier(k), sql.Placeholder()) for k in condition.keys()]
        
        query = sql.SQL("UPDATE {schema}.{table} SET {set} WHERE {where}").format(
            schema=sql.Identifier(schema),
            table=sql.Identifier(table),
            set=sql.SQL(', ').join(set_parts),
            where=sql.SQL(' AND ').join(where_parts)
        )
        
        values = list(data.values()) + list(condition.values())
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, values)
        except Exception as e:
            logger.error(f"Error actualizando datos en {schema}.{table}: {e}")
            raise
