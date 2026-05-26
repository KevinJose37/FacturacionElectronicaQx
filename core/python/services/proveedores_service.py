"""Servicio de consultas para la página de proveedores."""

import logging
from datetime import datetime, timezone

from config import load_yaml_config, load_yaml_queries
from core.python.db import get_pool
from metadata.common_metadata import DefaultTextos
from metadata.dashboard_metadata import FormatoTiempo

logger = logging.getLogger(__name__)

_settings = load_yaml_config('settings.yaml')
_proveedores_cfg = _settings.get('proveedores', {})

_QUERIES = load_yaml_queries('services/queries_services.yml').get('proveedores', {})


async def listar_proveedores() -> list:
    """Lista proveedores (emisores) con métricas de facturación.

    Returns:
        Lista de proveedores con tasa de validación, estado y última sincronización.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['listar'])
            filas = await cur.fetchall()

    umbral_activo = int(_proveedores_cfg.get('umbral_activo', 90))
    umbral_revision = int(_proveedores_cfg.get('umbral_revision', 70))
    ahora = datetime.now(tz=timezone.utc)

    resultado = []
    for r in filas:
        total = r[3]
        xml_validadas = r[4]
        pdf_validadas = r[5]
        tasa_xml = round((xml_validadas / max(total, 1)) * 100, 1)
        tasa_pdf = round((pdf_validadas / max(total, 1)) * 100, 1)

        ultima = r[6]
        if ultima:
            if ultima.tzinfo is None:
                ultima = ultima.replace(tzinfo=timezone.utc)
            delta_min = int((ahora - ultima).total_seconds() / 60)
            sync_texto = FormatoTiempo.desde_minutos(delta_min)
        else:
            sync_texto = FormatoTiempo.nunca

        if tasa_xml >= umbral_activo:
            estado = 'active'
        elif tasa_xml >= umbral_revision:
            estado = 'review'
        else:
            estado = 'blocked'

        resultado.append({
            'name': r[1] or DefaultTextos.sin_nombre,
            'nit': r[0],
            'invoices': total,
            'validRateXml': tasa_xml,
            'validRatePdf': tasa_pdf,
            'status': estado,
            'lastSync': sync_texto,
        })
    return resultado


async def obtener_estadisticas() -> dict:
    """Calcula estadísticas agregadas de proveedores.

    Returns:
        Diccionario con total, activos, tasa_promedio.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(_QUERIES['estadisticas'])
            row = await cur.fetchone()

    estadisticas = {
        'total': row[0],
        'activos': row[1],
        'tasa_promedio': round(float(row[2]), 1),
    }
    return estadisticas
