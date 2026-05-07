"""Envío de correos electrónicos para alertas críticas.

Usa la misma cuenta de Gmail configurada para la ingesta de facturas
(EMAIL_USER / EMAIL_PASSWORD) para enviar notificaciones por SMTP.
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import Optional

from metadata.alertas_metadata import CodigoPrioridad, MensajesAlerta

logger = logging.getLogger(__name__)


def _construir_html_alerta(
    titulo: str,
    mensaje: str,
    prioridad: str,
    contexto: Optional[dict] = None,
) -> str:
    """Construye el cuerpo HTML del correo de alerta.

    Args:
        titulo: Título de la alerta.
        mensaje: Descripción detallada.
        prioridad: Código de prioridad (CRITICA, ALTA, etc.).
        contexto: Datos adicionales para mostrar en el correo.

    Returns:
        String HTML del cuerpo del correo.
    """
    color = CodigoPrioridad.COLORES_UI.get(prioridad, '#6B7280')
    fecha = datetime.now(tz=timezone.utc).strftime('%d/%m/%Y %H:%M UTC')

    filas_contexto = ''
    if contexto:
        for clave, valor in contexto.items():
            clave_fmt = clave.replace('_', ' ').title()
            filas_contexto += (
                f'<tr>'
                f'<td style="padding:6px 12px;font-weight:600;color:#374151;">{clave_fmt}</td>'
                f'<td style="padding:6px 12px;color:#6B7280;">{valor}</td>'
                f'</tr>'
            )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;background:#F9FAFB;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:24px auto;">
    <tr>
      <td style="background:{color};padding:16px 24px;border-radius:8px 8px 0 0;">
        <h1 style="margin:0;font-size:18px;color:#FFFFFF;">
          ⚠️ Alerta {prioridad} — Facturación Electrónica
        </h1>
      </td>
    </tr>
    <tr>
      <td style="background:#FFFFFF;padding:24px;border:1px solid #E5E7EB;border-top:none;">
        <h2 style="margin:0 0 12px;font-size:16px;color:#111827;">{titulo}</h2>
        <p style="margin:0 0 16px;color:#4B5563;line-height:1.5;">{mensaje}</p>
        {f'''
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#F3F4F6;border-radius:6px;margin-bottom:16px;">
          {filas_contexto}
        </table>
        ''' if filas_contexto else ''}
        <p style="margin:0;font-size:12px;color:#9CA3AF;">
          Generado automáticamente el {fecha} por el Sistema de Facturación Electrónica Quipux.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""
    return html


def enviar_alerta_critica(
    destinatarios: list[str],
    titulo: str,
    mensaje: str,
    prioridad: str = CodigoPrioridad.critica,
    contexto: Optional[dict] = None,
    smtp_host: str = 'smtp.gmail.com',
    smtp_port: int = 465,
) -> bool:
    """Envía un correo de alerta crítica vía Gmail SMTP.

    Usa las variables de entorno EMAIL_USER y EMAIL_PASSWORD
    (las mismas que el listener de ingesta).

    Args:
        destinatarios: Lista de direcciones de correo.
        titulo: Título de la alerta.
        mensaje: Descripción detallada.
        prioridad: Código de prioridad para el template.
        contexto: Datos adicionales estructurados.
        smtp_host: Servidor SMTP.
        smtp_port: Puerto SMTP (465 para SSL).

    Returns:
        True si el correo se envió exitosamente, False en caso contrario.
    """
    remitente = os.environ.get('EMAIL_USER', '')
    password = os.environ.get('EMAIL_PASSWORD', '')

    if not remitente or not password:
        logger.warning('EMAIL_USER o EMAIL_PASSWORD no configurados. No se envía correo de alerta.')
        return False

    if not destinatarios:
        logger.warning('No hay destinatarios configurados para alertas por correo.')
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = remitente
        msg['To'] = ', '.join(destinatarios)
        msg['Subject'] = f'[ALERTA {prioridad}] {titulo}'

        # Cuerpo texto plano (fallback)
        texto_plano = f'ALERTA {prioridad}: {titulo}\n\n{mensaje}'
        if contexto:
            texto_plano += '\n\nDetalles:\n'
            for k, v in contexto.items():
                texto_plano += f'  - {k}: {v}\n'

        msg.attach(MIMEText(texto_plano, 'plain', 'utf-8'))

        # Cuerpo HTML
        html = _construir_html_alerta(titulo, mensaje, prioridad, contexto)
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as servidor:
            servidor.login(remitente, password)
            servidor.send_message(msg)

        logger.info(MensajesAlerta.alerta_email_enviado, titulo)
        return True

    except Exception as exc:
        logger.error(MensajesAlerta.alerta_email_error, exc)
        return False
