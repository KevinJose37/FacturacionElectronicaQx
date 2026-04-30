"""Servicio de consultas para la página de proveedores."""

import logging

from core.db import get_pool

logger = logging.getLogger(__name__)


async def listar_proveedores() -> list:
    """Lista proveedores (emisores) con métricas de facturación.

    Returns:
        Lista de proveedores con conteo de facturas y tasa de validación.
    """
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT t.numero_documento, t.nombre_comercial, t.razon_social, '
                'COUNT(f.id_factura) as total_facturas, '
                'COUNT(f.id_factura) FILTER (WHERE f.id_estado_proceso IN (7, 9)) as validadas, '
                'MAX(f.fecha_creacion) as ultima_sync '
                'FROM facturacion.tercero t '
                'LEFT JOIN facturacion.factura f ON t.id_tercero = f.id_tercero_emisor '
                'WHERE t.id_rol_tercero = 1 '
                'GROUP BY t.id_tercero '
                'ORDER BY total_facturas DESC'
            )
            filas = await cur.fetchall()

    from datetime import datetime, timezone
    ahora = datetime.now(tz=timezone.utc)

    resultado = []
    for r in filas:
        total = r[3]
        validadas = r[4]
        tasa = round((validadas / max(total, 1)) * 100, 1)
        ultima = r[5]

        if ultima:
            if ultima.tzinfo is None:
                from datetime import timezone as tz
                ultima = ultima.replace(tzinfo=tz.utc)
            delta_min = int((ahora - ultima).total_seconds() / 60)
            if delta_min < 60:
                sync_texto = f'hace {delta_min}m'
            elif delta_min < 1440:
                sync_texto = f'hace {delta_min // 60}h'
            else:
                sync_texto = f'hace {delta_min // 1440}d'
        else:
            sync_texto = 'nunca'

        estado = 'active' if tasa >= 90 else 'review' if tasa >= 70 else 'blocked'

        resultado.append({
            'name': r[1] or r[2],
            'cuit': r[0],
            'invoices': total,
            'validRate': tasa,
            'status': estado,
            'erp': 'SAP',
            'lastSync': sync_texto,
        })
    return resultado


async def obtener_estadisticas() -> dict:
    """Calcula estadísticas agregadas de proveedores.

    Returns:
        Diccionario con total, activos y tasa promedio de validación.
    """
    proveedores = await listar_proveedores()
    total = len(proveedores)
    activos = sum(1 for p in proveedores if p['status'] == 'active')
    tasa_promedio = round(sum(p['validRate'] for p in proveedores) / max(total, 1), 1)

    estadisticas = {
        'total': total,
        'activos': activos,
        'tasa_promedio': tasa_promedio,
    }
    return estadisticas
