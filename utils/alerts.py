"""Gestor de alertas para el sistema de facturación electrónica.

Persiste cada alerta en la tabla FACTURACION.ALERTA y, si la prioridad
es CRITICA, envía un correo electrónico a los destinatarios configurados.
Mantiene el logging como canal secundario para trazabilidad.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, List, Optional

import yaml

from metadata.alertas_metadata import (
    CodigoPrioridad,
    CodigoTipoAlerta,
    MensajesAlerta,
    TitulosAlerta,
)
from utils.alertas_repository import AlertasRepository
from utils.email_sender import enviar_alerta_critica

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'settings.yaml'


def _cargar_config_alertas() -> dict:
    """Carga la sección 'alerts' del archivo de configuración."""
    try:
        if _CONFIG_PATH.exists():
            with _CONFIG_PATH.open('r', encoding='utf-8') as fh:
                cfg = yaml.safe_load(fh) or {}
            return cfg.get('alerts', {})
    except Exception:
        pass
    return {}


class AlertManager:
    """Gestiona la emisión y persistencia de alertas del sistema.

    Cada método público:
    1. Persiste la alerta en BD (FACTURACION.ALERTA).
    2. Si la prioridad es CRITICA, envía correo a los destinatarios.
    3. Escribe en el log como canal secundario.
    """

    def __init__(self, config: Optional[dict] = None):
        """Inicializa el gestor con la configuración de alertas.

        Args:
            config: Diccionario de configuración general del sistema.
                    Se extrae la sección 'alerts' si está presente.
        """
        alerts_cfg = (config or {}).get('alerts', {})
        if not alerts_cfg:
            alerts_cfg = _cargar_config_alertas()

        self.enabled = alerts_cfg.get('enabled', True)
        self.destinatarios = alerts_cfg.get('email_destinatarios', [])
        self.smtp_host = alerts_cfg.get('smtp_host', 'smtp.gmail.com')
        self.smtp_port = int(alerts_cfg.get('smtp_port', 465))
        self._repo = AlertasRepository()

    # ------------------------------------------------------------------
    # Método interno unificado
    # ------------------------------------------------------------------

    def _emitir(
        self,
        codigo_tipo: str,
        titulo: str,
        mensaje: str,
        codigo_prioridad: Optional[str] = None,
        contexto: Optional[dict] = None,
        correo_id: Optional[int] = None,
        adjunto_id: Optional[int] = None,
        factura_id: Optional[int] = None,
        conn: Any = None,
    ) -> int:
        """Persiste una alerta y dispara correo si corresponde.

        Args:
            codigo_tipo: Tipo de alerta (FK a TIPO_ALERTA).
            titulo: Título para la UI.
            mensaje: Descripción detallada.
            codigo_prioridad: Prioridad explícita. Si None, usa default del tipo.
            contexto: Datos adicionales.
            correo_id: FK a CORREO_ENTRANTE.
            adjunto_id: FK a ADJUNTOS_CORREO.
            factura_id: FK a FACTURA.
            conn: Conexión BD activa (opcional, para reusar la transacción).

        Returns:
            ID de la alerta creada, o -1 si falló.
        """
        if not self.enabled:
            return -1

        # Resolver prioridad
        prioridad = codigo_prioridad or CodigoTipoAlerta.PRIORIDAD_DEFAULT.get(
            codigo_tipo, CodigoPrioridad.media,
        )

        # 1. Evaluar si corresponde enviar correo
        correo_enviado = False
        if prioridad == CodigoPrioridad.critica and self.destinatarios:
            correo_enviado = enviar_alerta_critica(
                destinatarios=self.destinatarios,
                titulo=titulo,
                mensaje=mensaje,
                prioridad=prioridad,
                contexto=contexto,
                smtp_host=self.smtp_host,
                smtp_port=self.smtp_port,
            )

        # 2. Persistir en BD
        id_alerta = self._repo.insertar_alerta(
            conn=conn,
            codigo_tipo=codigo_tipo,
            titulo=titulo,
            mensaje=mensaje,
            codigo_prioridad=prioridad,
            contexto=contexto,
            correo_id=correo_id,
            adjunto_id=adjunto_id,
            factura_id=factura_id,
            correo_enviado=correo_enviado,
        )

        # 3. Log como canal secundario
        nivel_log = {
            CodigoPrioridad.critica: logging.CRITICAL,
            CodigoPrioridad.alta: logging.WARNING,
            CodigoPrioridad.media: logging.INFO,
            CodigoPrioridad.baja: logging.DEBUG,
        }.get(prioridad, logging.INFO)

        log_msg = f'ALERTA [{prioridad}]: {titulo}'
        if contexto:
            log_msg += f' | Contexto: {contexto}'
        logger.log(nivel_log, log_msg)

        return id_alerta

    # ------------------------------------------------------------------
    # Métodos públicos — Prioridad CRITICA
    # ------------------------------------------------------------------

    def malware_detectado(
        self,
        nombre_archivo: str,
        nivel_riesgo: str,
        detalle: Optional[str] = None,
        adjunto_id: Optional[int] = None,
        correo_id: Optional[int] = None,
    ) -> int:
        """Notifica detección de malware en un archivo.

        Returns:
            ID de la alerta creada.
        """
        titulo = TitulosAlerta.malware_detectado.format(archivo=nombre_archivo)
        mensaje = f'ClamAV detectó una amenaza en el archivo {nombre_archivo}.'
        if detalle:
            mensaje += f' Detalle: {detalle}'

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.malware_detectado,
            titulo=titulo,
            mensaje=mensaje,
            contexto={
                'archivo': nombre_archivo,
                'nivel_riesgo': nivel_riesgo,
                'detalle': detalle,
            },
            adjunto_id=adjunto_id,
            correo_id=correo_id,
        )

    def error_conexion(
        self,
        tipo: str,
        detalle: str,
    ) -> int:
        """Notifica un error de conexión (IMAP, DB, S3).

        Returns:
            ID de la alerta creada.
        """
        titulo = TitulosAlerta.conexion_fallida.format(servicio=tipo)
        mensaje = f'No se pudo establecer conexión con {tipo}. Detalle: {detalle}'

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.conexion_fallida,
            titulo=titulo,
            mensaje=mensaje,
            contexto={'servicio': tipo, 'detalle': detalle},
        )

    def bot_inactivo(
        self,
        ultimo_ciclo: str,
        minutos_inactivo: int,
    ) -> int:
        """Notifica que el bot de extracción dejó de funcionar.

        Args:
            ultimo_ciclo: Timestamp del último ciclo exitoso.
            minutos_inactivo: Minutos desde el último ciclo.

        Returns:
            ID de la alerta creada.
        """
        titulo = TitulosAlerta.bot_inactivo.format(minutos=minutos_inactivo)
        mensaje = (
            f'El bot de extracción de correos no ha ejecutado un ciclo '
            f'en los últimos {minutos_inactivo} minutos. '
            f'Último ciclo exitoso: {ultimo_ciclo}.'
        )

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.bot_inactivo,
            titulo=titulo,
            mensaje=mensaje,
            contexto={
                'ultimo_ciclo': ultimo_ciclo,
                'minutos_inactivo': minutos_inactivo,
            },
        )

    # ------------------------------------------------------------------
    # Métodos públicos — Prioridad ALTA
    # ------------------------------------------------------------------

    def factura_rechazada(
        self,
        motivo: str,
        nit: Optional[str] = None,
        num_factura: Optional[str] = None,
        factura_id: Optional[int] = None,
        adjunto_id: Optional[int] = None,
        correo_id: Optional[int] = None,
    ) -> int:
        """Notifica que una factura no pasó las validaciones DIAN.

        Returns:
            ID de la alerta creada.
        """
        titulo = TitulosAlerta.factura_rechazada.format(motivo=motivo[:80])
        mensaje = f'La factura no cumple con los requisitos normativos DIAN: {motivo}'

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.factura_rechazada,
            titulo=titulo,
            mensaje=mensaje,
            contexto={
                'motivo': motivo,
                'nit': nit,
                'num_factura': num_factura,
            },
            factura_id=factura_id,
            adjunto_id=adjunto_id,
            correo_id=correo_id,
        )

    def vencimiento_proximo(
        self,
        factura_id: int,
        numero_factura: str,
        dias_restantes: int,
        nit_emisor: Optional[str] = None,
    ) -> int:
        """Notifica que una factura está próxima a vencer sin aceptación.

        Returns:
            ID de la alerta creada.
        """
        titulo = TitulosAlerta.vencimiento_proximo.format(
            numero_factura=numero_factura, dias=dias_restantes,
        )
        mensaje = (
            f'La factura {numero_factura} vence en {dias_restantes} día(s) '
            f'y no tiene un evento de aceptación DIAN registrado.'
        )

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.vencimiento_proximo,
            titulo=titulo,
            mensaje=mensaje,
            contexto={
                'numero_factura': numero_factura,
                'dias_restantes': dias_restantes,
                'nit_emisor': nit_emisor,
            },
            factura_id=factura_id,
        )

    def max_reintentos_excedido(
        self,
        adjunto_id: int,
        cufe: Optional[str] = None,
        intentos: int = 0,
        error: Optional[str] = None,
        conn: Any = None,
    ) -> int:
        """Notifica que una factura agotó los reintentos de procesamiento.

        Returns:
            ID de la alerta creada.
        """
        cufe_corto = (cufe or 'desconocido')[:20]
        titulo = TitulosAlerta.max_reintentos.format(cufe=cufe_corto)
        mensaje = (
            f'El procesamiento de la factura con CUFE {cufe_corto}... '
            f'falló después de {intentos} intentos.'
        )
        if error:
            mensaje += f' Último error: {error}'

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.max_reintentos,
            titulo=titulo,
            mensaje=mensaje,
            contexto={
                'cufe': cufe,
                'intentos': intentos,
                'ultimo_error': error,
            },
            adjunto_id=adjunto_id,
            conn=conn,
        )

    # ------------------------------------------------------------------
    # Métodos públicos — Prioridad MEDIA
    # ------------------------------------------------------------------

    def adjunto_incompleto(
        self,
        email_uid: str,
        archivos: List[str],
        motivo: str,
        correo_id: Optional[int] = None,
        adjunto_id: Optional[int] = None,
    ) -> int:
        """Notifica que un ZIP no contiene los archivos necesarios (XML/PDF).

        Returns:
            ID de la alerta creada.
        """
        titulo = TitulosAlerta.zip_incompleto.format(motivo=motivo[:80])
        mensaje = f'Adjunto incompleto en correo {email_uid}: {motivo}'

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.zip_incompleto,
            titulo=titulo,
            mensaje=mensaje,
            contexto={
                'email_uid': email_uid,
                'archivos_encontrados': archivos,
                'motivo': motivo,
            },
            correo_id=correo_id,
            adjunto_id=adjunto_id,
        )

    def pdf_faltante(
        self,
        nombre_xml: str,
        adjunto_id: Optional[int] = None,
        correo_id: Optional[int] = None,
    ) -> int:
        """Notifica que una factura fue procesada sin PDF.

        Returns:
            ID de la alerta creada.
        """
        titulo = TitulosAlerta.pdf_faltante
        mensaje = f'El XML {nombre_xml} fue procesado sin un PDF correspondiente.'

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.pdf_faltante,
            titulo=titulo,
            mensaje=mensaje,
            contexto={'nombre_xml': nombre_xml},
            adjunto_id=adjunto_id,
            correo_id=correo_id,
        )

    def correo_sin_adjuntos(
        self,
        email_uid: str,
        motivo: str,
        correo_id: Optional[int] = None,
    ) -> int:
        """Notifica que un correo de facturación no tiene adjuntos válidos.

        Returns:
            ID de la alerta creada.
        """
        titulo = TitulosAlerta.correo_sin_adjuntos
        mensaje = f'El correo {email_uid} fue identificado como facturación pero no contiene adjuntos válidos: {motivo}'

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.correo_sin_adjuntos,
            titulo=titulo,
            mensaje=mensaje,
            contexto={'email_uid': email_uid, 'motivo': motivo},
            correo_id=correo_id,
        )

    def verificacion_grafica_fallida(
        self,
        num_factura: str,
        metodos: list,
        campos_fallidos: dict,
        factura_id: Optional[int] = None,
        adjunto_id: Optional[int] = None,
        correo_id: Optional[int] = None,
    ) -> int:
        """Notifica que la verificación gráfica del PDF falló."""
        titulo = TitulosAlerta.verificacion_grafica_fallida.format(numero_factura=num_factura)
        mensaje = f'La verificación gráfica del PDF falló para la factura {num_factura}.'
        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.verificacion_grafica_fallida,
            titulo=titulo,
            mensaje=mensaje,
            contexto={
                'metodos_intentados': metodos,
                'campos_fallidos': campos_fallidos,
            },
            factura_id=factura_id,
            adjunto_id=adjunto_id,
            correo_id=correo_id,
        )


    # ------------------------------------------------------------------
    # Métodos públicos — Prioridad BAJA
    # ------------------------------------------------------------------

    def validacion_parcial(
        self,
        factura_id: int,
        numero_factura: str,
        validaciones_fallidas: List[str],
        adjunto_id: Optional[int] = None,
        conn: Any = None,
    ) -> int:
        """Notifica que una factura se registró con validaciones fallidas.

        Returns:
            ID de la alerta creada.
        """
        titulo = TitulosAlerta.validacion_parcial.format(numero_factura=numero_factura)
        fallidas_str = ', '.join(validaciones_fallidas[:10])
        mensaje = (
            f'La factura {numero_factura} fue registrada pero tiene '
            f'{len(validaciones_fallidas)} validación(es) fallida(s): {fallidas_str}'
        )

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.validacion_parcial,
            titulo=titulo,
            mensaje=mensaje,
            contexto={
                'numero_factura': numero_factura,
                'validaciones_fallidas': validaciones_fallidas,
                'total_fallidas': len(validaciones_fallidas),
            },
            factura_id=factura_id,
            adjunto_id=adjunto_id,
            conn=conn,
        )

    def duplicado_detectado(
        self,
        cufe: str,
        sha256: Optional[str] = None,
        adjunto_id: Optional[int] = None,
    ) -> int:
        """Notifica que una factura duplicada fue detectada y omitida.

        Returns:
            ID de la alerta creada.
        """
        cufe_corto = cufe[:20]
        titulo = TitulosAlerta.duplicado_detectado.format(cufe=cufe_corto)
        mensaje = f'Se detectó un duplicado de la factura CUFE {cufe_corto}... y fue omitido.'

        return self._emitir(
            codigo_tipo=CodigoTipoAlerta.duplicado_detectado,
            titulo=titulo,
            mensaje=mensaje,
            contexto={'cufe': cufe, 'sha256': sha256},
            adjunto_id=adjunto_id,
        )
