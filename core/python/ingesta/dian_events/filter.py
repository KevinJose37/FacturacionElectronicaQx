"""Filtro especializado para detectar correos de eventos DIAN de CEN Financiero."""

import logging
import re
from dataclasses import dataclass

from metadata.eventos_dian_metadata import EventosDianMetadata

logger = logging.getLogger(__name__)


@dataclass
class DianEventFilterResult:
    """Resultado de la evaluación del filtro de eventos DIAN.

    Attributes:
        is_dian_event: Indica si el correo cumple con los criterios de evento DIAN.
        event_code: Código del evento detectado (030, 032, 033).
        reason: Motivo por el cual se descartó el correo.
    """

    is_dian_event: bool
    event_code: str | None = None
    reason: str | None = None


class DianEventFilter:
    """Filtro para correos de eventos DIAN de CEN Financiero.

    Reglas:
    1. Remitente: Configurado en EventosDianMetadata.
    2. Asunto: Empieza con 'Evento' y termina con un código permitido.
    """

    def evaluate(self, sender: str, subject: str) -> DianEventFilterResult:
        """Evalúa si un correo corresponde a un evento DIAN autorizado.

        Args:
            sender: Dirección de correo del remitente.
            subject: Asunto del correo electrónico.

        Returns:
            DianEventFilterResult con el veredicto del filtro.
        """
        resultado = None

        # 1. Validar remitente
        sender_email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
        sender_email = sender_email_match.group(0) if sender_email_match else sender

        sender_lower = sender_email.lower()
        is_authorized = any(s.lower() == sender_lower for s in EventosDianMetadata.remitentes_autorizados)

        if not is_authorized:
            resultado = DianEventFilterResult(False, reason=f'Remitente no autorizado: {sender_email}')
        else:
            # 2. Validar asunto
            subject_clean = subject.strip()
            if not subject_clean.lower().startswith('evento'):
                resultado = DianEventFilterResult(False, reason='El asunto no comienza con "Evento"')
            else:
                # 3. Extraer código de evento al final (después del último ;)
                parts = subject_clean.split(';')
                if len(parts) < 2:
                    resultado = DianEventFilterResult(False, reason='Asunto sin delimitador ";"')
                else:
                    event_code = parts[-1].strip()

                    if event_code not in EventosDianMetadata.codigos_permitidos:
                        resultado = DianEventFilterResult(
                            False,
                            reason=f'Código de evento no permitido: {event_code}',
                        )
                    else:
                        resultado = DianEventFilterResult(True, event_code=event_code)

        return resultado
