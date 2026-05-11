"""Puntos de entrada de la API para disparar procesos de ingesta."""

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from config import get_config
from core import EmailListener

from core.python.facturas.invoice_processor import InvoiceProcessor

router = APIRouter(prefix='/api/webhook', tags=['webhook'])

logger = logging.getLogger(__name__)

_WEBHOOK_SECRET = get_config('WEBHOOK_SECRET', '')


def _run_ingesta() -> None:
    """Ejecuta el listener de correos y luego procesa las facturas pendientes."""
    try:
        # 1. Ingesta: descargar de correo -> extraer ZIPs -> subir a S3 -> EVENTO_INGESTA
        EmailListener().run()
        
        # 2. Procesamiento: EVENTO_INGESTA -> Validaciones DIAN -> FACTURA
        logger.info('Iniciando procesamiento de facturas pendientes...')
        processor = InvoiceProcessor()
        resultados = processor.procesar_pendientes()
        logger.info('Procesamiento completado: %s', resultados)
        
    except Exception as e:
        logger.exception('Falla en background task de ingesta: %s', e)


@router.post('/gmail')
async def gmail_webhook(
    background_tasks: BackgroundTasks,
    x_webhook_secret: str = Header(None),
) -> dict:
    """Recibe notificaciones de Gmail e inicia la ingesta.

    Args:
        background_tasks: Gestor de tareas en segundo plano.
        x_webhook_secret: Token de validación (Header).

    Raises:
        HTTPException: Si el secreto es inválido o no está configurado.
    """
    if not _WEBHOOK_SECRET or x_webhook_secret != _WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail='Unauthorized')

    background_tasks.add_task(_run_ingesta)
    respuesta = {'status': 'accepted'}
    return respuesta
