"""Puntos de entrada de la API para disparar procesos de ingesta."""

import os
import logging
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks
from core import EmailListener

router = APIRouter(
    prefix="/webhook",
    tags=["webhook"]
)

logger = logging.getLogger("api.ingesta")

# Secreto obligatorio
WEBHOOK_SECRET = os.environ["WEBHOOK_SECRET"]

def run_ingesta():
    """Ejecuta el listener de correos de forma asíncrona."""
    try:
        EmailListener().run()
    except Exception as e:
        logger.error(f"Falla en background task: {e}")

@router.post("/gmail")
async def gmail_webhook(
    background_tasks: BackgroundTasks,
    x_webhook_secret: str = Header(None)
):
    """Recibe notificaciones de Gmail e inicia la ingesta.

    Args:
        background_tasks: Gestor de tareas en segundo plano.
        x_webhook_secret: Token de validación (Header).

    Returns:
        dict: Estado de la petición.

    Raises:
        HTTPException: Si el secreto es inválido.
    """
    if x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    background_tasks.add_task(run_ingesta)
    return {"status": "accepted"}
