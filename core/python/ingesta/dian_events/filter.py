"""Filtro especializado para detectar correos de eventos DIAN de CEN Financiero."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from metadata.eventos_dian_metadata import EventosDianMetadata

logger = logging.getLogger(__name__)


@dataclass
class DianEventFilterResult:
    is_dian_event: bool
    event_code: Optional[str] = None
    reason: Optional[str] = None

class DianEventFilter:
    """Filtro para correos de eventos DIAN de CEN Financiero.
    
    Reglas:
    1. Remitente: Configurado en EventosDianMetadata
    2. Asunto: Empieza con "Evento" y termina con un código permitido
    """
    
    def evaluate(self, sender: str, subject: str) -> DianEventFilterResult:
        # 1. Validar remitente
        # Extraer solo el email si viene con nombre: "Nombre <email>"
        sender_email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
        sender_email = sender_email_match.group(0) if sender_email_match else sender
        
        sender_lower = sender_email.lower()
        is_authorized = any(s.lower() == sender_lower for s in EventosDianMetadata.remitentes_autorizados)
        
        if not is_authorized:
            return DianEventFilterResult(False, reason=f"Remitente no autorizado: {sender_email}")
            
        # 2. Validar asunto
        subject = subject.strip()
        if not subject.lower().startswith("evento"):
            return DianEventFilterResult(False, reason="El asunto no comienza con 'Evento'")
            
        # 3. Extraer código de evento al final (después del último ;)
        parts = subject.split(";")
        if len(parts) < 2:
            return DianEventFilterResult(False, reason="Asunto sin delimitador ';'")
            
        event_code = parts[-1].strip()
        
        if event_code not in EventosDianMetadata.codigos_permitidos:
            return DianEventFilterResult(False, reason=f"Código de evento no permitido: {event_code}")
            
        return DianEventFilterResult(True, event_code=event_code)
