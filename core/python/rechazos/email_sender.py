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

    def enviar_correo(self, destinatario, asunto, cuerpo, max_reintentos=3):
        """Envía un correo electrónico con política de reintentos.
        
        Returns:
            bool: True si se envió exitosamente, False de lo contrario.
        """
        if not self.user or not self.password:
            logger.error("No se han configurado las credenciales de correo (EMAIL_USER/EMAIL_PASSWORD)")
            return False

        intentos = 0
        while intentos < max_reintentos:
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
                
                logger.info(f"Correo enviado exitosamente a {destinatario}")
                return True
            except Exception as e:
                intentos += 1
                logger.warning(f"Intento {intentos} fallido enviando correo a {destinatario}: {e}")
                if intentos < max_reintentos:
                    time.sleep(2 ** intentos) # Exponential backoff
        
        logger.error(f"No se pudo enviar el correo a {destinatario} tras {max_reintentos} intentos.")
        return False
