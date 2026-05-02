"""Gestor de alertas para el sistema de facturación electrónica.

Permite notificar errores críticos, rechazos de facturas y problemas de seguridad
a través de diferentes canales (logs, email, etc.).
"""

import logging
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


class AlertManager:
    """Gestiona la emisión de alertas del sistema."""

    def __init__(self, config: dict):
        """Inicializa el gestor con la configuración de alertas.

        Args:
            config: Diccionario de configuración (sección 'alerts').
        """
        self.config = config.get("alerts", {})
        self.enabled = self.config.get("enabled", True)
        self.channels = self.config.get("channels", ["log"])

    def _notificar(self, nivel: str, mensaje: str, contexto: Optional[dict] = None):
        """Envía una notificación por los canales configurados.

        Args:
            nivel: Nivel de la alerta (INFO, WARNING, ERROR, CRITICAL).
            mensaje: Texto de la alerta.
            contexto: Datos adicionales para la alerta.
        """
        if not self.enabled:
            return

        formatted_msg = f"ALERTA [{nivel}]: {mensaje}"
        if contexto:
            formatted_msg += f" | Contexto: {contexto}"

        # Siempre enviamos a log si está configurado
        if "log" in self.channels:
            if nivel == "INFO":
                logger.info(formatted_msg)
            elif nivel == "WARNING":
                logger.warning(formatted_msg)
            elif nivel == "ERROR":
                logger.error(formatted_msg)
            elif nivel == "CRITICAL":
                logger.critical(formatted_msg)

        # Aquí se podrían implementar otros canales como 'email', 'slack', etc.
        # if "email" in self.channels:
        #     self._enviar_email(nivel, mensaje, contexto)

    def error_conexion(self, tipo: str, detalle: str):
        """Notifica un error de conexión (IMAP, DB, etc.)."""
        self._notificar("ERROR", f"Error de conexión en {tipo}", {"detalle": detalle})

    def factura_rechazada(self, motivo: str, nit: Optional[str] = None, num_factura: Optional[str] = None):
        """Notifica que un correo no pasó el filtro de facturación."""
        self._notificar("WARNING", f"Factura rechazada: {motivo}", {
            "nit": nit,
            "num_factura": num_factura
        })

    def adjunto_incompleto(self, email_uid: str, archivos: List[str], motivo: str):
        """Notifica que el ZIP no contiene los archivos necesarios (XML/PDF)."""
        self._notificar("ERROR", f"Adjunto incompleto: {motivo}", {
            "email_uid": email_uid,
            "archivos_encontrados": archivos
        })

    def malware_detectado(self, nombre_archivo: str, nivel_riesgo: str):
        """Notifica detección de malware en un archivo."""
        self._notificar("CRITICAL", f"MALWARE DETECTADO: {nombre_archivo}", {
            "nivel_riesgo": nivel_riesgo
        })

    def verificacion_grafica_fallida(self, num_factura: str, metodos: list, campos_fallidos: dict):
        """Notifica que la verificación gráfica del PDF falló."""
        self._notificar("WARNING", f"Verificación gráfica fallida para factura {num_factura}", {
            "metodos_intentados": metodos,
            "campos_fallidos": campos_fallidos
        })
