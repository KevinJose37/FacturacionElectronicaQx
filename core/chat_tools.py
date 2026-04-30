"""Herramientas de consulta a BD para el chatbot Innti.

Define funciones que el LLM puede invocar vía function calling para
buscar datos específicos en la base de datos del sistema de facturación.
"""

import logging
from datetime import datetime, timezone

from core.db import get_pool

logger = logging.getLogger(__name__)


# ── Definiciones de Tools para el LLM (OpenAI function calling format) ──

TOOL_DEFINITIONS = [
    {
        'type': 'function',
        'function': {
            'name': 'buscar_facturas',
            'description': (
                'Busca facturas en la base de datos. Permite filtrar por estado, '
                'proveedor, tipo de documento, o número de factura. '
                'Usar cuando el usuario pregunta por facturas específicas, las últimas facturas, '
                'facturas de un proveedor, facturas rechazadas, etc.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'estado': {
                        'type': 'string',
                        'enum': ['validada', 'rechazada', 'pendiente', 'error', 'todas'],
                        'description': 'Filtrar por estado de la factura.',
                    },
                    'proveedor': {
                        'type': 'string',
                        'description': 'Nombre (parcial) del proveedor emisor.',
                    },
                    'tipo_documento': {
                        'type': 'string',
                        'enum': ['FE', 'NC', 'ND', 'DS'],
                        'description': 'Tipo: FE=Factura, NC=Nota crédito, ND=Nota débito, DS=Doc soporte.',
                    },
                    'numero_factura': {
                        'type': 'string',
                        'description': 'Número o prefijo de la factura a buscar.',
                    },
                    'limite': {
                        'type': 'string',
                        'description': 'Máximo de resultados (default "10", max "25").',
                    },
                    'ordenar_por': {
                        'type': 'string',
                        'enum': ['reciente', 'antiguo', 'monto_alto', 'monto_bajo'],
                        'description': 'Criterio de ordenamiento.',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'listar_proveedores',
            'description': (
                'Lista los proveedores registrados con estadísticas. '
                'Usar cuando preguntan por proveedores, emisores, empresas, o datos de contacto.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'nombre': {
                        'type': 'string',
                        'description': 'Filtrar por nombre (parcial) del proveedor.',
                    },
                    'limite': {
                        'type': 'string',
                        'description': 'Máximo de resultados (default "10").',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'detalle_factura',
            'description': (
                'Obtiene el detalle completo de una factura específica. '
                'Usar cuando preguntan por el detalle de una factura en particular.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'numero_factura': {
                        'type': 'string',
                        'description': 'Número de factura (ej: SETT-990, FE-001).',
                    },
                    'cufe': {
                        'type': 'string',
                        'description': 'CUFE de la factura.',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'buscar_rechazos',
            'description': (
                'Busca facturas rechazadas con motivos. '
                'Usar cuando preguntan por rechazos, errores o causas de rechazo.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'proveedor': {
                        'type': 'string',
                        'description': 'Filtrar rechazos por proveedor (nombre parcial).',
                    },
                    'limite': {
                        'type': 'string',
                        'description': 'Máximo de resultados (default "10").',
                    },
                },
                'required': [],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'ver_logs_recientes',
            'description': (
                'Consulta los logs más recientes del sistema. '
                'Usar cuando preguntan por actividad reciente, errores del sistema o eventos.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'solo_errores': {
                        'type': 'string',
                        'enum': ['true', 'false'],
                        'description': '"true" para solo errores, "false" para todos.',
                    },
                    'limite': {
                        'type': 'string',
                        'description': 'Máximo de logs (default "10").',
                    },
                },
                'required': [],
            },
        },
    },
]


# ── Helpers ─────────────────────────────────────────────────────────

def _parse_int(val, default: int = 10, max_val: int = 25) -> int:
    """Parsea un valor a int con default y max."""
    try:
        return min(max(int(val), 1), max_val)
    except (TypeError, ValueError):
        return default


def _parse_bool(val, default: bool = False) -> bool:
    """Parsea un valor a bool."""
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ('true', '1', 'yes', 'si')
    return default


# ── Constantes ──────────────────────────────────────────────────────

MAPA_ESTADOS = {
    'validada': (7, 9),
    'rechazada': (8, 10),
    'pendiente': (5, 6),
    'error': (10,),
}

MAPA_TIPOS = {
    'FE': 'Factura electrónica',
    'NC': 'Nota crédito',
    'ND': 'Nota débito',
    'DS': 'Documento soporte',
}

MAPA_ORDEN = {
    'reciente': 'f.fecha_creacion DESC',
    'antiguo': 'f.fecha_creacion ASC',
    'monto_alto': 'f.valor_total DESC',
    'monto_bajo': 'f.valor_total ASC',
}


# ── Implementaciones de las Tools ───────────────────────────────────

async def buscar_facturas(
    estado: str = 'todas',
    proveedor: str = '',
    tipo_documento: str = '',
    numero_factura: str = '',
    limite: str = '10',
    ordenar_por: str = 'reciente',
) -> str:
    """Busca facturas en la BD con filtros opcionales."""
    pool = get_pool()
    lim = _parse_int(limite)
    order = MAPA_ORDEN.get(ordenar_por, 'f.fecha_creacion DESC')

    conditions = []
    params = []

    if estado != 'todas' and estado in MAPA_ESTADOS:
        placeholders = ','.join(['%s'] * len(MAPA_ESTADOS[estado]))
        conditions.append(f'f.id_estado_proceso IN ({placeholders})')
        params.extend(MAPA_ESTADOS[estado])

    if proveedor:
        conditions.append('t.nombre_comercial ILIKE %s')
        params.append(f'%{proveedor}%')

    if tipo_documento:
        conditions.append('f.tipo_documento = %s')
        params.append(tipo_documento)

    if numero_factura:
        conditions.append("(f.numero_factura ILIKE %s OR f.prefijo_facturacion ILIKE %s)")
        params.extend([f'%{numero_factura}%', f'%{numero_factura}%'])

    where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
    params.append(lim)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f'SELECT f.prefijo_facturacion, f.numero_factura, '
                f't.nombre_comercial, ep.descripcion, '
                f'f.valor_total, f.fecha_expedicion, f.tipo_documento, f.cufe '
                f'FROM facturacion.factura f '
                f'JOIN facturacion.tercero t ON f.id_tercero_emisor = t.id_tercero '
                f'JOIN facturacion.tipo_estado_proceso ep ON f.id_estado_proceso = ep.id_estado_proceso '
                f'{where} ORDER BY {order} LIMIT %s',
                params,
            )
            filas = await cur.fetchall()

    if not filas:
        return 'No se encontraron facturas con los filtros especificados.'

    resultados = []
    for r in filas:
        num = f'{r[0]}-{r[1]}' if r[0] else r[1]
        tipo = MAPA_TIPOS.get(r[6], r[6]) if r[6] else 'N/A'
        fecha = r[5].strftime('%d/%m/%Y %H:%M') if r[5] else 'Sin fecha'
        monto = f'${r[4]:,.0f}' if r[4] else '$0'
        resultados.append(
            f'• {num} | {r[2]} | {r[3]} | {tipo} | {monto} | {fecha}'
        )

    header = f'Se encontraron {len(filas)} factura(s):\n'
    return header + '\n'.join(resultados)


async def listar_proveedores(nombre: str = '', limite: str = '10') -> str:
    """Lista proveedores con sus estadísticas."""
    pool = get_pool()
    lim = _parse_int(limite)

    where = ''
    params = []
    if nombre:
        where = 'WHERE t.nombre_comercial ILIKE %s'
        params.append(f'%{nombre}%')

    params.append(lim)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f'SELECT t.nombre_comercial, t.numero_documento, '
                f't.correo_contacto, t.telefono_contacto, '
                f'COUNT(f.id_factura) as total_facturas, '
                f'COUNT(f.id_factura) FILTER (WHERE f.id_estado_proceso IN (7,9)) as validadas, '
                f'COUNT(f.id_factura) FILTER (WHERE f.id_estado_proceso IN (8,10)) as rechazadas '
                f'FROM facturacion.tercero t '
                f'LEFT JOIN facturacion.factura f ON t.id_tercero = f.id_tercero_emisor '
                f'{where} '
                f'GROUP BY t.id_tercero, t.nombre_comercial, t.numero_documento, '
                f't.correo_contacto, t.telefono_contacto '
                f'ORDER BY total_facturas DESC LIMIT %s',
                params,
            )
            filas = await cur.fetchall()

    if not filas:
        return 'No se encontraron proveedores.'

    resultados = []
    for r in filas:
        tasa = round((r[5] / max(r[4], 1)) * 100, 1) if r[4] else 0
        contacto = r[2] or r[3] or 'Sin contacto'
        resultados.append(
            f'• {r[0]} (NIT: {r[1]}) — {r[4]} facturas '
            f'({r[5]} validadas, {r[6]} rechazadas, tasa: {tasa}%) — {contacto}'
        )

    return f'{len(filas)} proveedor(es):\n' + '\n'.join(resultados)


async def detalle_factura(numero_factura: str = '', cufe: str = '') -> str:
    """Obtiene el detalle completo de una factura."""
    pool = get_pool()

    conditions = []
    params = []
    if numero_factura:
        conditions.append("(f.prefijo_facturacion || '-' || f.numero_factura ILIKE %s "
                          "OR f.numero_factura ILIKE %s)")
        params.extend([f'%{numero_factura}%', f'%{numero_factura}%'])
    if cufe:
        conditions.append('f.cufe ILIKE %s')
        params.append(f'%{cufe}%')

    if not conditions:
        return 'Debes especificar un número de factura o CUFE para buscar.'

    where = 'WHERE ' + ' AND '.join(conditions)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f'SELECT f.prefijo_facturacion, f.numero_factura, f.cufe, '
                f'f.tipo_documento, f.valor_total, f.codigo_moneda, '
                f'f.fecha_generacion, f.fecha_expedicion, f.fecha_vencimiento, '
                f'te.nombre_comercial as emisor, te.numero_documento as nit_emisor, '
                f'ta.nombre_comercial as adquiriente, ta.numero_documento as nit_adquiriente, '
                f'ep.descripcion as estado, '
                f'f.fecha_creacion, f.fecha_actualizacion '
                f'FROM facturacion.factura f '
                f'JOIN facturacion.tercero te ON f.id_tercero_emisor = te.id_tercero '
                f'LEFT JOIN facturacion.tercero ta ON f.id_tercero_adquiriente = ta.id_tercero '
                f'JOIN facturacion.tipo_estado_proceso ep ON f.id_estado_proceso = ep.id_estado_proceso '
                f'{where} LIMIT 1',
                params,
            )
            row = await cur.fetchone()

    if not row:
        return f'No se encontró factura con número "{numero_factura or cufe}".'

    tipo = MAPA_TIPOS.get(row[3], row[3]) if row[3] else 'N/A'
    monto = f'${row[4]:,.0f} {row[5]}' if row[4] else 'Sin monto'
    f_exp = row[7].strftime('%d/%m/%Y %H:%M') if row[7] else 'N/A'
    f_venc = row[8].strftime('%d/%m/%Y') if row[8] else 'N/A'
    f_gen = row[6].strftime('%d/%m/%Y %H:%M') if row[6] else 'N/A'

    return (
        f'DETALLE DE FACTURA {row[0]}-{row[1]}\n'
        f'  Tipo: {tipo}\n'
        f'  CUFE: {row[2][:40]}...\n'
        f'  Estado: {row[13]}\n'
        f'  Monto: {monto}\n'
        f'  Fecha expedición: {f_exp}\n'
        f'  Fecha vencimiento: {f_venc}\n'
        f'  Fecha generación: {f_gen}\n'
        f'  Emisor: {row[9]} (NIT: {row[10]})\n'
        f'  Adquiriente: {row[11] or "N/A"} (NIT: {row[12] or "N/A"})\n'
    )


async def buscar_rechazos(proveedor: str = '', limite: str = '10') -> str:
    """Busca facturas rechazadas con sus motivos."""
    pool = get_pool()
    lim = _parse_int(limite)

    where_extra = ''
    params = []
    if proveedor:
        where_extra = 'AND t.nombre_comercial ILIKE %s'
        params.append(f'%{proveedor}%')
    params.append(lim)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f'SELECT f.prefijo_facturacion, f.numero_factura, '
                f't.nombre_comercial, ep.descripcion, '
                f'f.valor_total, f.fecha_creacion '
                f'FROM facturacion.factura f '
                f'JOIN facturacion.tercero t ON f.id_tercero_emisor = t.id_tercero '
                f'JOIN facturacion.tipo_estado_proceso ep ON f.id_estado_proceso = ep.id_estado_proceso '
                f'WHERE f.id_estado_proceso IN (8, 10) {where_extra} '
                f'ORDER BY f.fecha_creacion DESC LIMIT %s',
                params,
            )
            filas = await cur.fetchall()

    if not filas:
        return 'No se encontraron rechazos con los filtros especificados.'

    resultados = []
    for r in filas:
        num = f'{r[0]}-{r[1]}' if r[0] else r[1]
        monto = f'${r[4]:,.0f}' if r[4] else '$0'
        fecha = r[5].strftime('%d/%m/%Y') if r[5] else 'N/A'
        resultados.append(
            f'• {num} | {r[2]} | {r[3]} | {monto} | {fecha}'
        )

    return f'{len(filas)} rechazo(s):\n' + '\n'.join(resultados)


async def ver_logs_recientes(solo_errores: str = 'false', limite: str = '10') -> str:
    """Consulta los logs más recientes del sistema."""
    pool = get_pool()
    lim = _parse_int(limite)
    only_errors = _parse_bool(solo_errores)

    where = 'WHERE lp.detalle_error IS NOT NULL' if only_errors else ''
    params = [lim]

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f'SELECT lp.codigo_etapa, lp.detalle_error, lp.fecha_inicio, '
                f'lp.fecha_fin '
                f'FROM facturacion.log_proceso lp '
                f'{where} '
                f'ORDER BY lp.fecha_inicio DESC LIMIT %s',
                params,
            )
            filas = await cur.fetchall()

    if not filas:
        return 'No se encontraron logs recientes.'

    resultados = []
    for r in filas:
        fecha = r[2].strftime('%d/%m/%Y %H:%M') if r[2] else 'N/A'
        duracion = ''
        if r[2] and r[3]:
            delta = (r[3] - r[2]).total_seconds()
            duracion = f' ({delta:.1f}s)'
        estado = 'ERROR' if r[1] else 'OK'
        error_text = f'\n  Error: {r[1][:80]}' if r[1] else ''
        resultados.append(
            f'• [{fecha}] {r[0]} - {estado}{duracion}{error_text}'
        )

    return f'{len(filas)} log(s) recientes:\n' + '\n'.join(resultados)


# ── Dispatcher ──────────────────────────────────────────────────────

TOOL_HANDLERS = {
    'buscar_facturas': buscar_facturas,
    'listar_proveedores': listar_proveedores,
    'detalle_factura': detalle_factura,
    'buscar_rechazos': buscar_rechazos,
    'ver_logs_recientes': ver_logs_recientes,
}


async def execute_tool(name: str, arguments: dict) -> str:
    """Ejecuta una tool por nombre con los argumentos dados."""
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return f'Tool desconocida: {name}'

    try:
        result = await handler(**arguments)
        return result
    except Exception as e:
        logger.error('Error ejecutando tool %s: %s', name, e)
        return f'Error al ejecutar la consulta: {e}'
