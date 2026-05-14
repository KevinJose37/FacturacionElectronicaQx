"""Filtro especializado para detectar correos de eventos DIAN de CEN Financiero."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class DianEventFilterResult:
    is_dian_event: bool
    event_code: Optional[str] = None
    reason: Optional[str] = None

class DianEventFilter:
    """Filtro para correos de eventos DIAN de CEN Financiero.
    
    Reglas:
    1. Remitente: facturacionelectronicaqx@gmail.com (Para pruebas)
    2. Asunto: Empieza con "Evento" y termina con ";030", ";032" o ";033"
    """
    
    # Durante pruebas permitimos el remitente de pruebas
    ALLOWED_SENDERS = [
        "facturacionelectronicaqx@gmail.com",
        "FacturaCTSColombia@cenbiz.com",
        "FacturaCTSColombia@cenbiz"
    ]
    ALLOWED_CODES = {"030", "032", "033"}
    
    def evaluate(self, sender: str, subject: str) -> DianEventFilterResult:
        # 1. Validar remitente
        # Extraer solo el email si viene con nombre: "Nombre <email>"
        sender_email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
        sender_email = sender_email_match.group(0) if sender_email_match else sender
        
        sender_lower = sender_email.lower()
        is_authorized = any(s.lower() == sender_lower for s in self.ALLOWED_SENDERS)
        
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
        
        if event_code not in self.ALLOWED_CODES:
            return DianEventFilterResult(False, reason=f"Código de evento no permitido: {event_code}")
            
        # 4. Extraer CUFE o número de factura si es posible (formato CEN suele ser NIT;NOMBRE;NUMERO;TIPO;...)
        # Según el requerimiento, nos interesa el evento al final.
        
        return DianEventFilterResult(True, event_code=event_code)
