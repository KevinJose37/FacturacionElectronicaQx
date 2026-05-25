"""Servicio de alertas de eventos DIAN.

Genera reportes de facturas que no han recibido los eventos DIAN
requeridos (030, 032, 033) y facturas que recibieron evento de
rechazo (031), agrupados por año y mes.

Solo aplica para facturas con forma_pago diferente a 'Contado'
(codigo_forma_pago != '1').
"""

import logging
from datetime import datetime, timezone

from config import load_yaml_queries
from core.python.db import get_pool
from metadata.alertas import EtiquetasAlerta
from metadata.fechas_metadata import MesesEspanol

logger = logging.getLogger(__name__)

_QUERIES = load_yaml_queries('alertas/eventos.yml').get('alertas_dian', {})


def _agrupar_por_anio_mes(filas: list) -> dict:
    """Agrupa filas (anio, mes, cantidad) en estructura jerárquica.

    Args:
        filas: Lista de tuplas (anio, mes, cantidad).

    Returns:
        Diccionario anidado {año: {mes_nombre: cantidad}}.
    """
    resultado = {}
    for anio, mes, cantidad in filas:
        anio_str = str(anio)
        # Obtener nombre del mes desde metadata y capitalizar
        mes_raw = MesesEspanol.mapa.get(mes, f'Mes {mes}')
        mes_nombre = mes_raw.capitalize()

        if anio_str not in resultado:
            resultado[anio_str] = {}
        resultado[anio_str][mes_nombre] = cantidad
    return resultado


async def obtener_alertas_dian(fecha_corte: datetime | None = None) -> dict:
    """Ejecuta las 4 consultas de alertas DIAN y retorna el reporte.

    Args:
        fecha_corte:
            Fecha límite para considerar facturas. Si es None,
            se intenta leer la última ejecución exitosa del scheduler.
            Si no hay archivo, se usa datetime.now(UTC).

    Returns:
        Diccionario con las 4 alertas, cada una contiene:
        - label: descripción de la alerta
        - total: cantidad total de facturas afectadas
        - detalle: desglose por año y mes
    """
    import json
    import os

    # Si no se provee fecha_corte, es una consulta de visualización.
    # Intentamos obtener los datos de la última ejecución programada real.
    if fecha_corte is None:
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ruta_cache = os.path.join(raiz, 'temp', 'alertas_dian_ultimo.json')
        
        if os.path.exists(ruta_cache):
            try:
                with open(ruta_cache, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                logger.warning('Error al leer caché de alertas DIAN, recalculando...')

    if fecha_corte is None:
        fecha_corte = datetime.now(tz=timezone.utc)

    pool = get_pool()
    alertas = {}
    totales = {}

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Obtener resumen de totales en una sola query
            query_totales = _QUERIES.get('resumen_totales', '')
            if query_totales:
                await cur.execute(query_totales, (fecha_corte,))
                row = await cur.fetchone()
                if row:
                    totales = {
                        'sin_evento_030': row[0],
                        'sin_evento_032': row[1],
                        'sin_evento_033': row[2],
                        'con_evento_rechazo': row[3],
                    }

            # Obtener detalle por año y mes para cada tipo de alerta
            claves_consulta = [
                'sin_evento_030',
                'sin_evento_032',
                'sin_evento_033',
                'con_evento_rechazo',
            ]

            for clave in claves_consulta:
                query = _QUERIES.get(clave, '')
                if not query:
                    logger.warning('Query no encontrada: alertas_dian.%s', clave)
                    continue

                await cur.execute(query, (fecha_corte,))
                filas = await cur.fetchall()
                detalle = _agrupar_por_anio_mes(filas)

                alertas[clave] = {
                    'label': EtiquetasAlerta.mapa.get(clave, clave),
                    'total': totales.get(clave, 0),
                    'detalle': detalle,
                }

    logger.info(
        'Alertas DIAN generadas — sin_030=%s, sin_032=%s, sin_033=%s, rechazo=%s',
        totales.get('sin_evento_030', 0),
        totales.get('sin_evento_032', 0),
        totales.get('sin_evento_033', 0),
        totales.get('con_evento_rechazo', 0),
    )

    resultado = {
        'fecha_ejecucion': fecha_corte.isoformat(),
        'alertas': alertas,
    }
    return resultado
