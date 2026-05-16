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
        AVISO_HABEAS_DATA = """

--------------------------------------------------
Tratamiento de información proveniente de facturación electrónica DIAN

La información procesada por la plataforma puede provenir de documentos electrónicos validados por la Dirección de Impuestos y Aduanas Nacionales (DIAN), incluyendo facturas electrónicas, notas crédito/débito, documentos soporte y eventos asociados.

El tratamiento de dicha información se realiza exclusivamente para fines tributarios, contables, administrativos, operativos y comerciales autorizados por el titular de los datos o habilitados por la normativa aplicable.

La plataforma actúa como Encargado del Tratamiento respecto de la información administrada por sus clientes, quienes ostentan la calidad de Responsables del Tratamiento conforme a la Ley 1581 de 2012.

La información es almacenada bajo controles de seguridad técnicos y organizacionales adecuados, incluyendo mecanismos de cifrado, control de acceso y trazabilidad de operaciones.

Los datos personales serán conservados únicamente durante el tiempo necesario para cumplir las finalidades autorizadas y las obligaciones legales aplicables, tras lo cual serán eliminados o anonimizados de manera segura.
"""
        cuerpo_con_aviso = cuerpo + AVISO_HABEAS_DATA
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
                msg.attach(MIMEText(cuerpo_con_aviso, 'plain'))

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
