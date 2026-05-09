"""Módulo orquestador para el manejo de rechazos y devoluciones."""

import json
import logging
import os
from datetime import datetime
 
from config import get_queries_email
from core.python.db import get_pool
from core.python.rechazos.email_sender import EmailSender
 
logger = logging.getLogger(__name__)
 
_QUERIES = get_queries_email().get('rechazos', {})
 
 
class RechazoHandler:
    """Gestiona la lógica de rechazos, notificaciones y registro de devoluciones."""
 
    def __init__(self) -> None:
        """Inicializa el handler de rechazos."""
        self.email_sender = EmailSender()
        self.plantilla_path = os.path.join('input', 'email', 'plantilla_rechazo.txt')
 
    def _cargar_plantilla(self) -> str:
        """Carga la plantilla de correo desde el sistema de archivos."""
        with open(self.plantilla_path, 'r', encoding='utf-8') as f:
            return f.read()
 
    async def procesar_rechazo(
        self,
        correo_id: int,
        motivo_principal: str,
        inconsistencias: list[str] | None = None,
    ) -> None:
        """Orquesta el flujo de rechazo y notificación al proveedor.
 
        Args:
            correo_id: ID único del correo en la tabla correo_entrante.
            motivo_principal: Descripción general de la falla.
            inconsistencias: Listado detallado de errores encontrados.
        """
        pool = get_pool()
        inconsistencias = inconsistencias or []
 
        async with pool.connection() as conn:
            # 1. Obtener datos del remitente y asunto original
            async with conn.cursor() as cur:
                await cur.execute(_QUERIES['obtener_datos_correo'], (correo_id,))
                correo_data = await cur.fetchone()
                if not correo_data:
                    logger.error('No se encontró el correo con ID %s', correo_id)
                    return
 
                remitente, asunto = correo_data
 
                # 2. Registrar devolución inicial (PENDIENTE)
                await cur.execute(
                    _QUERIES['registrar_devolucion'],
                    (
                        correo_id,
                        remitente,
                        remitente,
                        asunto,
                        motivo_principal,
                        json.dumps(inconsistencias),
                    ),
                )
                id_devolucion = (await cur.fetchone())[0]
                await conn.commit()
 
            # 3. Preparar y enviar correo
            cuerpo_plantilla = self._cargar_plantilla()
            listado_str = '\n'.join([f'- {inc}' for inc in inconsistencias])
            if not listado_str:
                listado_str = f'- {motivo_principal}'
 
            cuerpo_final = cuerpo_plantilla.format(
                remitente=remitente,
                asunto=asunto,
                listado_inconsistencias=listado_str,
            )
 
            asunto_notif = f'RECHAZO DE FACTURA: {asunto}'
            exito = self.email_sender.enviar_correo(remitente, asunto_notif, cuerpo_final)
 
            if exito:
                logger.info(
                    'Correo de rechazo enviado exitosamente a %s para la factura: %s',
                    remitente,
                    asunto,
                )
 
            # 4. Actualizar tabla de devoluciones y log de proceso
            async with conn.cursor() as cur:
                estado = 'ENVIADO' if exito else 'FALLIDO'
                error_msg = None if exito else 'Error en servidor SMTP tras reintentos'
 
                await cur.execute(
                    _QUERIES['actualizar_estado_devolucion'],
                    (estado, error_msg, id_devolucion),
                )
 
                # Registrar el fallo en proceso_ingesta si el correo no se envió
                if not exito:
                    await cur.execute(_QUERIES['registrar_fallo_proceso'], (correo_id,))
                await conn.commit()
 
    async def manejar_sin_adjuntos(self, correo_id: int) -> None:
        """Caso específico donde el correo no trae adjuntos pero cumple el asunto."""
        motivo = 'No se encontró información adjunta correspondiente a factura electrónica (ZIP/XML).'
        await self.procesar_rechazo(correo_id, motivo)

