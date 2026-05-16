"""Scheduler de alertas DIAN — se ejecuta diariamente a las 12:00 PM.

Realiza un conteo de las facturas que no han recibido los eventos DIAN
requeridos (030, 032, 033) y aquellas que recibieron evento de rechazo (031).
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

# Agregar raíz del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from core.python.db import close_pool, init_pool
from core.python.services.alertas_dian_service import obtener_alertas_dian
from metadata.alertas import ConfigScheduler

load_dotenv()

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
)
logger = logging.getLogger('alertas_dian_scheduler')


def _formatear_reporte(resultado: dict) -> str:
    """Formatea el resultado de alertas DIAN para logging legible.

    Args:
        resultado: Diccionario retornado por obtener_alertas_dian.

    Returns:
        Cadena formateada con el reporte completo.
    """
    lineas = [
        '',
        '=' * 60,
        '  REPORTE DE ALERTAS DIAN',
        f'  Fecha de ejecución: {resultado["fecha_ejecucion"]}',
        '=' * 60,
    ]

    for clave, alerta in resultado.get('alertas', {}).items():
        lineas.append('')
        lineas.append(f'  📋 {alerta["label"]}')
        lineas.append(f'     Total: {alerta["total"]}')

        detalle = alerta.get('detalle', {})
        if detalle:
            for anio, meses in detalle.items():
                lineas.append(f'     {anio}:')
                for mes_nombre, cantidad in meses.items():
                    lineas.append(f'       {mes_nombre}: {cantidad}')
        else:
            lineas.append('     (Sin registros)')

    lineas.append('')
    lineas.append('=' * 60)
    reporte = '\n'.join(lineas)
    return reporte


async def ejecutar_alertas() -> dict:
    """Ejecuta el ciclo completo de alertas DIAN.

    Returns:
        Diccionario con el resultado de las alertas.
    """
    await init_pool()
    try:
        ahora = datetime.now(tz=timezone.utc)
        logger.info('Iniciando conteo de alertas DIAN — corte: %s', ahora.isoformat())

        resultado = await obtener_alertas_dian(fecha_corte=ahora)
        reporte = _formatear_reporte(resultado)
        logger.info(reporte)

        # Guardar resultado en archivo JSON
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ruta_salida = os.path.join(raiz, 'temp', 'alertas_dian_ultimo.json')
        os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)

        with open(ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2)

        logger.info('Resultado guardado en %s', ruta_salida)
        respuesta = resultado
    finally:
        await close_pool()

    return respuesta


def _ya_ejecuto_hoy(ultima_ejecucion: str | None) -> bool:
    """Verifica si ya se ejecutó el proceso en el día actual.

    Args:
        ultima_ejecucion: Fecha ISO de la última ejecución.

    Returns:
        True si la fecha coincide con el día de hoy.
    """
    ya_ejecuto = False
    if ultima_ejecucion:
        try:
            fecha = datetime.fromisoformat(ultima_ejecucion)
            hoy = datetime.now().date()
            ya_ejecuto = fecha.date() == hoy
        except ValueError:
            ya_ejecuto = False

    return ya_ejecuto


def main() -> None:
    """Punto de entrada del scheduler."""
    parser = argparse.ArgumentParser(description='Scheduler de alertas DIAN')
    parser.add_argument(
        '--once',
        action='store_true',
        help='Ejecutar una sola vez y salir',
    )
    args = parser.parse_args()

    if args.once:
        logger.info('Modo --once: ejecutando alertas DIAN inmediatamente.')
        asyncio.run(ejecutar_alertas())
        return

    logger.info(
        'Scheduler iniciado — esperando ejecución diaria a las %02d:%02d',
        ConfigScheduler.hora_ejecucion,
        ConfigScheduler.minuto_ejecucion,
    )

    ultima_fecha_ejecucion = None

    while True:
        ahora = datetime.now()
        es_hora = (
            ahora.hour == ConfigScheduler.hora_ejecucion
            and ahora.minute == ConfigScheduler.minuto_ejecucion
        )
        ya_ejecuto = _ya_ejecuto_hoy(ultima_fecha_ejecucion)

        if es_hora and not ya_ejecuto:
            logger.info('Son las 12:00 PM — ejecutando alertas DIAN.')
            try:
                asyncio.run(ejecutar_alertas())
                ultima_fecha_ejecucion = ahora.isoformat()
            except Exception:
                logger.exception('Error durante la ejecución de alertas DIAN')
        else:
            proxima = ahora.replace(
                hour=ConfigScheduler.hora_ejecucion,
                minute=ConfigScheduler.minuto_ejecucion,
                second=0,
                microsecond=0
            )
            if ahora >= proxima:
                proxima += timedelta(days=1)

            delta = (proxima - ahora).total_seconds()
            if delta > 3600:
                logger.debug('Próxima ejecución en %.0f horas.', delta / 3600)

        time.sleep(ConfigScheduler.segundos_espera)


if __name__ == '__main__':
    main()
