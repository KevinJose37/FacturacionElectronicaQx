"""Módulo orquestador para el manejo de rechazos y devoluciones."""

import os
import logging
import json
from datetime import datetime
from core.python.db import get_pool
from core.python.rechazos.email_sender import EmailSender

logger = logging.getLogger(__name__)

class RechazoHandler:
    """Gestiona la lógica de rechazos, notificaciones y registro de devoluciones."""

    def __init__(self):
        self.email_sender = EmailSender()
        self.plantilla_path = os.path.join("metadata", "plantilla_rechazo.txt")

    def _cargar_plantilla(self):
        with open(self.plantilla_path, "r", encoding="utf-8") as f:
            return f.read()

    async def procesar_rechazo(self, correo_id, motivo_principal, inconsistencias=None):
        """
        Orquesta el flujo de rechazo:
        1. Obtiene datos del correo original.
        2. Registra en la tabla de devoluciones.
        3. Envía correo al proveedor.
        4. Actualiza estado de la devolución.
        """
        pool = get_pool()
        inconsistencias = inconsistencias or []
        
        async with pool.connection() as conn:
            # 1. Obtener datos del remitente y asunto original
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT remitente, asunto FROM facturacion.correo_entrante WHERE correo_id = %s",
                    (correo_id,)
                )
                correo_data = await cur.fetchone()
                if not correo_data:
                    logger.error(f"No se encontró el correo con ID {correo_id}")
                    return
                
                remitente, asunto = correo_data

                # 2. Registrar devolución inicial (PENDIENTE)
                await cur.execute(
                    """
                    INSERT INTO facturacion.devolucion (
                        correo_id, remitente_original, destinatario_notif, 
                        asunto_original, motivo_principal, inconsistencias_json
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id_devolucion
                    """,
                    (correo_id, remitente, remitente, asunto, motivo_principal, json.dumps(inconsistencias))
                )
                id_devolucion = (await cur.fetchone())[0]
                await conn.commit()

            # 3. Preparar y enviar correo
            cuerpo_plantilla = self._cargar_plantilla()
            listado_str = "\n".join([f"- {inc}" for inc in inconsistencias])
            if not listado_str:
                listado_str = f"- {motivo_principal}"

            cuerpo_final = cuerpo_plantilla.format(
                remitente=remitente,
                asunto=asunto,
                listado_inconsistencias=listado_str
            )

            asunto_notif = f"RECHAZO DE FACTURA: {asunto}"
            exito = self.email_sender.enviar_correo(remitente, asunto_notif, cuerpo_final)

            if exito:
                logger.info(f"Correo de rechazo enviado exitosamente a {remitente} para la factura: {asunto}")

            # 4. Actualizar tabla de devoluciones y log de proceso
            async with conn.cursor() as cur:
                estado = "ENVIADO" if exito else "FALLIDO"
                error_msg = None if exito else "Error en servidor SMTP tras reintentos"
                
                await cur.execute(
                    """
                    UPDATE facturacion.devolucion 
                    SET estado_notificacion = %s, error_envio = %s, intentos_envio = intentos_envio + 1
                    WHERE id_devolucion = %s
                    """,
                    (estado, error_msg, id_devolucion)
                )
                
                # Registrar el fallo en proceso_ingesta si el correo no se envió
                if not exito:
                    await cur.execute(
                        """
                        INSERT INTO facturacion.proceso_ingesta (
                            adjunto_id, id_proceso, id_estado, observacion, id_error
                        ) SELECT adjunto_id, 24, 4, 'Fallo al enviar correo de rechazo', 17
                        FROM facturacion.adjuntos_correo WHERE correo_id = %s LIMIT 1
                        """,
                        (correo_id,)
                    )
                await conn.commit()

    async def manejar_sin_adjuntos(self, correo_id):
        """Caso específico donde el correo no trae adjuntos pero cumple el asunto."""
        motivo = "No se encontró información adjunta correspondiente a factura electrónica (ZIP/XML)."
        await self.procesar_rechazo(correo_id, motivo)
