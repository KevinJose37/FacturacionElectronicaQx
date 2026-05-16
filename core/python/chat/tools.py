"""Herramientas de consulta a BD para el chatbot Innti.

Define funciones que el LLM puede invocar vía function calling para
buscar datos específicos en la base de datos del sistema de facturación.
"""

import logging
import sys

from config import get_tool_definitions, load_yaml_queries
from core.python.db import get_pool
from metadata.chat_metadata import MensajesRespuesta
from metadata.common_metadata import DefaultTextos
from metadata.factura_metadata import EstadosFactura, OrdenFacturas, TiposDocumento

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = get_tool_definitions()

_QUERIES = load_yaml_queries('chat/queries_chat.yml')
_FILTROS = _QUERIES.get('filtros', {})


def _parse_int(val, default: int = 10, max_val: int = 25) -> int:
    """Parsea un valor a int con default y máximo.

    Args:
        val: Valor a convertir.
        default: Valor por defecto si la conversión falla.
        max_val: Valor máximo permitido.
    """
    try:
        resultado = min(max(int(val), 1), max_val)
    except (TypeError, ValueError):
        resultado = default
    return resultado


def _parse_bool(val, default: bool = False) -> bool:
    """Parsea un valor a booleano.

    Args:
        val: Valor a convertir.
        default: Valor por defecto si la conversión falla.
    """
    if isinstance(val, bool):
        resultado = val
    elif isinstance(val, str):
        resultado = val.lower() in ('true', '1', 'yes', 'si')
    else:
        resultado = default
    return resultado


def _formato_numero_factura(prefijo, numero) -> str:
    """Formatea el número de factura con prefijo opcional."""
    resultado = f'{prefijo}-{numero}' if prefijo else str(numero)
    return resultado


def _formato_monto(valor, moneda: str = '') -> str:
    """Formatea un valor monetario para presentación.

    Args:
        valor: Monto numérico o None.
        moneda: Código ISO de moneda opcional.
    """
    if not valor:
        resultado = DefaultTextos.sin_monto if not moneda else DefaultTextos.sin_monto_detalle
    elif moneda:
        resultado = f'${valor:,.0f} {moneda}'
    else:
        resultado = f'${valor:,.0f}'
    return resultado


def _formato_fecha(fecha, con_hora: bool = True) -> str:
    """Formatea una fecha para presentación.

    Args:
        fecha: Objeto datetime o None.
        con_hora: Si True usa formato con hora, si False solo fecha.
    """
    if not fecha:
        resultado = DefaultTextos.no_aplica
    elif con_hora:
        resultado = fecha.strftime(DefaultTextos.formato_fecha_hora)
    else:
        resultado = fecha.strftime(DefaultTextos.formato_fecha)
    return resultado


async def buscar_facturas(
    estado: str = 'todas',
    proveedor: str = '',
    tipo_documento: str = '',
    numero_factura: str = '',
    limite: str = '10',
    ordenar_por: str = 'reciente',
) -> str:
    """Busca facturas en la BD con filtros opcionales.

    Args:
        estado: Filtro por estado de la factura.
        proveedor: Nombre parcial del proveedor emisor.
        tipo_documento: Código de tipo de documento (FE, NC, ND, DS).
        numero_factura: Número o prefijo de la factura.
        limite: Máximo de resultados.
        ordenar_por: Criterio de ordenamiento.
    """
    pool = get_pool()
    lim = _parse_int(limite)
    order = OrdenFacturas.mapa.get(ordenar_por, OrdenFacturas.reciente)

    conditions = []
    params = []

    if estado != 'todas' and estado in EstadosFactura.mapa_ids:
        ids_estado = EstadosFactura.mapa_ids[estado]
        placeholders = ','.join(['%s'] * len(ids_estado))
        conditions.append(_FILTROS['estado'].format(placeholders=placeholders))
        params.extend(ids_estado)

    if proveedor:
        conditions.append(_FILTROS['proveedor'])
        params.append(f'%{proveedor}%')

    if tipo_documento:
        conditions.append(_FILTROS['tipo_documento'])
        params.append(tipo_documento)

    if numero_factura:
        conditions.append(_FILTROS['numero_factura'])
        params.extend([f'%{numero_factura}%', f'%{numero_factura}%'])

    where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
    params.append(lim)

    query = _QUERIES['buscar_facturas'].format(where=where, order=order)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    if not filas:
        resultado = MensajesRespuesta.sin_facturas
    else:
        lineas = []
        for r in filas:
            num = _formato_numero_factura(r[0], r[1])
            tipo = TiposDocumento.mapa.get(r[6], r[6]) if r[6] else DefaultTextos.no_aplica
            fecha = _formato_fecha(r[5])
            monto = _formato_monto(r[4])
            lineas.append(f'• {num} | {r[2]} | {r[3]} | {tipo} | {monto} | {fecha}')
        resultado = f'Se encontraron {len(filas)} factura(s):\n' + '\n'.join(lineas)
    return resultado


async def listar_proveedores(nombre: str = '', limite: str = '10') -> str:
    """Lista proveedores con sus estadísticas.

    Args:
        nombre: Nombre parcial para filtrar proveedores.
        limite: Máximo de resultados.
    """
    pool = get_pool()
    lim = _parse_int(limite)

    where = ''
    params = []
    if nombre:
        where = 'WHERE ' + _FILTROS['proveedor']
        params.append(f'%{nombre}%')

    params.append(lim)
    ids_validadas = ','.join(str(i) for i in EstadosFactura.validada)
    ids_rechazadas = ','.join(str(i) for i in EstadosFactura.rechazada)

    query = _QUERIES['listar_proveedores'].format(
        where=where,
        ids_validadas=ids_validadas,
        ids_rechazadas=ids_rechazadas,
    )

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    if not filas:
        resultado = MensajesRespuesta.sin_proveedores
    else:
        lineas = []
        for r in filas:
            tasa = round((r[5] / max(r[4], 1)) * 100, 1) if r[4] else 0
            contacto = r[2] or r[3] or DefaultTextos.sin_contacto
            lineas.append(
                f'• {r[0]} (NIT: {r[1]}) — {r[4]} facturas '
                f'({r[5]} validadas, {r[6]} rechazadas, tasa: {tasa}%) — {contacto}'
            )
        resultado = f'{len(filas)} proveedor(es):\n' + '\n'.join(lineas)
    return resultado


async def detalle_factura(numero_factura: str = '', cufe: str = '') -> str:
    """Obtiene el detalle completo de una factura.

    Args:
        numero_factura: Número de factura a buscar.
        cufe: CUFE de la factura a buscar.
    """
    pool = get_pool()

    conditions = []
    params = []
    if numero_factura:
        conditions.append(_FILTROS['numero_factura_detalle'])
        params.extend([f'%{numero_factura}%', f'%{numero_factura}%'])
    if cufe:
        conditions.append(_FILTROS['cufe'])
        params.append(f'%{cufe}%')

    if not conditions:
        resultado = MensajesRespuesta.falta_identificador
        return resultado

    where = 'WHERE ' + ' AND '.join(conditions)
    query = _QUERIES['detalle_factura'].format(where=where)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            row = await cur.fetchone()

    if not row:
        resultado = MensajesRespuesta.sin_factura_detalle.format(identificador=numero_factura or cufe)
    else:
        tipo = TiposDocumento.mapa.get(row[3], row[3]) if row[3] else DefaultTextos.no_aplica
        monto = _formato_monto(row[4], row[5] or '')
        adquiriente = row[11] or DefaultTextos.no_aplica
        nit_adquiriente = row[12] or DefaultTextos.no_aplica

        resultado = (
            f'DETALLE DE FACTURA {row[0]}-{row[1]}\n'
            f'  Tipo: {tipo}\n'
            f'  CUFE: {row[2][:40]}...\n'
            f'  Estado: {row[13]}\n'
            f'  Monto: {monto}\n'
            f'  Fecha expedición: {_formato_fecha(row[7])}\n'
            f'  Fecha vencimiento: {_formato_fecha(row[8], con_hora=False)}\n'
            f'  Fecha generación: {_formato_fecha(row[6])}\n'
            f'  Emisor: {row[9]} (NIT: {row[10]})\n'
            f'  Adquiriente: {adquiriente} (NIT: {nit_adquiriente})\n'
        )
    return resultado


async def buscar_rechazos(proveedor: str = '', limite: str = '10') -> str:
    """Busca facturas rechazadas con sus motivos.

    Args:
        proveedor: Nombre parcial del proveedor para filtrar.
        limite: Máximo de resultados.
    """
    pool = get_pool()
    lim = _parse_int(limite)
    ids_rechazados = ','.join(str(i) for i in EstadosFactura.rechazada)

    where_extra = ''
    params = []
    if proveedor:
        where_extra = 'AND ' + _FILTROS['proveedor']
        params.append(f'%{proveedor}%')
    params.append(lim)

    query = _QUERIES['buscar_rechazos'].format(
        ids_rechazados=ids_rechazados,
        where_extra=where_extra,
    )

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    if not filas:
        resultado = MensajesRespuesta.sin_rechazos
    else:
        lineas = []
        for r in filas:
            num = _formato_numero_factura(r[0], r[1])
            monto = _formato_monto(r[4])
            fecha = _formato_fecha(r[5], con_hora=False)
            lineas.append(f'• {num} | {r[2]} | {r[3]} | {monto} | {fecha}')
        resultado = f'{len(filas)} rechazo(s):\n' + '\n'.join(lineas)
    return resultado


async def ver_logs_recientes(solo_errores: str = 'false', limite: str = '10') -> str:
    """Consulta los logs más recientes del sistema.

    Args:
        solo_errores: Si 'true', filtra solo logs con error.
        limite: Máximo de logs a retornar.
    """
    pool = get_pool()
    lim = _parse_int(limite)
    only_errors = _parse_bool(solo_errores)

    where = _FILTROS['solo_errores'] if only_errors else ''
    params = [lim]

    query = _QUERIES['ver_logs_recientes'].format(where=where)

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            filas = await cur.fetchall()

    if not filas:
        resultado = MensajesRespuesta.sin_logs
    else:
        lineas = []
        for r in filas:
            fecha = _formato_fecha(r[2])
            duracion = ''
            if r[2] and r[3]:
                delta = (r[3] - r[2]).total_seconds()
                duracion = f' ({delta:.1f}s)'
            estado = DefaultTextos.estado_error if r[1] else DefaultTextos.estado_ok
            error_text = f'\n  Error: {r[1][:80]}' if r[1] else ''
            lineas.append(f'• [{fecha}] {r[0]} - {estado}{duracion}{error_text}')
        resultado = f'{len(filas)} log(s) recientes:\n' + '\n'.join(lineas)
    return resultado


def _build_tool_handlers() -> dict:
    """Construye el mapeo de handlers dinámicamente desde TOOL_DEFINITIONS.

    Resuelve cada nombre de tool a la función correspondiente en este módulo.
    """
    modulo = sys.modules[__name__]
    handlers = {}
    for tool in TOOL_DEFINITIONS:
        nombre = tool['function']['name']
        handler = getattr(modulo, nombre, None)
        if handler and callable(handler):
            handlers[nombre] = handler
    return handlers


TOOL_HANDLERS = _build_tool_handlers()


async def execute_tool(name: str, arguments: dict) -> str:
    """Ejecuta una tool por nombre con los argumentos dados.

    Args:
        name: Nombre de la tool a ejecutar.
        arguments: Diccionario de argumentos para la tool.
    """
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        resultado = MensajesRespuesta.tool_desconocida.format(name=name)
        return resultado

    try:
        resultado = await handler(**arguments)
    except Exception as e:
        logger.error('Error ejecutando tool %s: %s', name, e)
        resultado = MensajesRespuesta.error_ejecucion.format(error=e)
    return resultado
