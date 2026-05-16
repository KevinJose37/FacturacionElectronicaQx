"""Paquete core de facturación electrónica.

Re-exporta los símbolos públicos desde los subpaquetes para
facilitar las importaciones desde los routers y main.py.

Uso:
    from core import init_pool, close_pool, get_pool
    from core import dashboard_service, facturas_service
    from core import chat_tools, cached
    from core import EmailListener
"""

# ── Base de datos y cache ──────────────────────────────────────────
from core.python.db import (                    # noqa: F401
    get_pool,
    init_pool,
    close_pool,
    cached,
    invalidate,
    DEFAULT_TTL,
)

# ── Servicios de consulta ──────────────────────────────────────────
from core.python.services import (              # noqa: F401
    alertas_dian_service,
    dashboard_service,
    facturas_service,
    logs_service,
    proveedores_service,
    rechazos_service,
    validaciones_service,
)

# ── Chat / Herramientas del LLM ───────────────────────────────────
from core.python.chat import tools as chat_tools  # noqa: F401

# ── Ingesta (email + queue) ───────────────────────────────────────
from core.python.ingesta import (               # noqa: F401
    EmailListener,
    get_publisher,
)

# ── Logs de proceso ───────────────────────────────────────────────
from core.python.logs_proceso import (          # noqa: F401
    registrar_proceso_ingesta,
)

# ── Schemas (modelos Pydantic) ────────────────────────────────────
from core.python.schemas import (               # noqa: F401
    DashboardResponse,
    FacturasPageResponse,
    ProveedoresPageResponse,
    ValidacionesPageResponse,
    RechazosPageResponse,
    LogsPageResponse,
)
