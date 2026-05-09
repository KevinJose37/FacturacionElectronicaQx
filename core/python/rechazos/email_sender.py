"""Módulo para el envío de correos electrónicos de rechazo y notificaciones."""

import smtplib
import logging
import os
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class EmailSender:
    """Clase para gestionar el envío de correos electrónicos con reintentos."""

    def __init__(self):
        self.user = os.environ.get('EMAIL_USER')
        self.password = os.environ.get('EMAIL_PASSWORD')
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def enviar_correo(
        self,
        destinatario: str,
        asunto: str,
        cuerpo: str,
        max_reintentos: int = 3,
    ) -> bool:
        """Envía un correo electrónico con política de reintentos.

        Args:
            destinatario: Dirección de correo del receptor.
            asunto: Título del mensaje.
            cuerpo: Contenido del mensaje en texto plano.
            max_reintentos: Cantidad máxima de intentos en caso de fallo.

        Returns:
            bool: True si se envió exitosamente, False de lo contrario.
        """
        exito = False
        if not self.user or not self.password:
            logger.error(
                'No se han configurado las credenciales de correo (EMAIL_USER/EMAIL_PASSWORD)',
            )
            return exito

        intentos = 0
        while intentos < max_reintentos and not exito:
            try:
                msg = MIMEMultipart()
                msg['From'] = self.user
                msg['To'] = destinatario
                msg['Subject'] = asunto
                msg.attach(MIMEText(cuerpo, 'plain'))

                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(msg)
                server.quit()

                logger.info('Correo enviado exitosamente a %s', destinatario)
                exito = True
            except Exception as e:
                intentos += 1
                logger.warning(
                    'Intento %d/%d fallido enviando correo a %s: %s',
                    intentos,
                    max_reintentos,
                    destinatario,
                    e,
                )
                if intentos < max_reintentos:
                    time.sleep(2**intentos)  # Exponential backoff

        if not exito:
            logger.error(
                'No se pudo enviar el correo a %s tras %d intentos.',
                destinatario,
                max_reintentos,
            )

        return exito
