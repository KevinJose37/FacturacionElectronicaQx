"""Modelos Pydantic para las respuestas de la API del dashboard."""

from datetime import datetime

from pydantic import BaseModel


class KpiResponse(BaseModel):
    """Indicador clave de rendimiento para el dashboard."""

    key: str
    label: str
    value: str
    delta: float
    spark: list
    color: str


class FlowStageResponse(BaseModel):
    """Etapa del flujo de facturación."""

    id: str
    label: str
    count: int
    status: str


class FacturaResumen(BaseModel):
    """Resumen de una factura para listados."""

    id: str
    provider: str
    type: str
    status: str
    amount: float
    date: str
    time: str


class ProveedorResumen(BaseModel):
    """Resumen de un proveedor para listados."""

    name: str
    cuit: str
    invoices: int
    valid_rate: float
    status: str
    erp: str
    last_sync: str


class ValidacionReglaResumen(BaseModel):
    """Resumen de una regla de validación."""

    code: str
    rule: str
    passed: int
    failed: int
    severity: str


class RechazoResumen(BaseModel):
    """Resumen de un rechazo para listados."""

    id: str
    provider: str
    reason: str
    rule: str
    date: str
    severity: str


class LogEntrada(BaseModel):
    """Entrada individual de log."""

    ts: str
    level: str
    source: str
    msg: str


class ActividadResumen(BaseModel):
    """Entrada de actividad reciente."""

    type: str
    text: str
    time: str


class ProviderBarData(BaseModel):
    """Datos de barra para gráfico de proveedores."""

    name: str
    facturas: int


class DocTypeData(BaseModel):
    """Datos de tipo de documento para gráfico de torta."""

    name: str
    value: int


class TrendData(BaseModel):
    """Datos de tendencia para gráfico de línea."""

    day: str
    procesadas: int
    validadas: int


class HeatmapCell(BaseModel):
    """Celda del heatmap de errores."""

    day: str
    hour: int
    value: int


class EstadisticasFacturas(BaseModel):
    """Estadísticas agregadas de facturas."""

    total: int
    validadas: int
    pendientes: int
    rechazadas: int
    monto_total: float


class EstadisticasProveedores(BaseModel):
    """Estadísticas agregadas de proveedores."""

    total: int
    activos: int
    tasa_promedio: float


class EstadisticasValidaciones(BaseModel):
    """Estadísticas agregadas de validaciones."""

    reglas_activas: int
    total_passed: int
    total_failed: int
    tasa_exito: float


class EstadisticasRechazos(BaseModel):
    """Estadísticas agregadas de rechazos."""

    rechazos_hoy: int
    severidad_alta: int
    reintentos: int
    tasa_rechazo: float


class CausaFrecuente(BaseModel):
    """Causa frecuente de rechazo."""

    rule: str
    count: int


class ConteoLogs(BaseModel):
    """Conteos de logs por nivel."""

    total_24h: int
    info: int
    warn: int
    error: int


# ── Respuestas de página completas ──


class DashboardResponse(BaseModel):
    """Respuesta completa del dashboard principal."""

    kpis: list
    flow_stages: list
    provider_data: list
    doc_type_data: list
    trend_data: list
    heatmap_data: list
    invoices: list
    activity: list


class FacturasPageResponse(BaseModel):
    """Respuesta completa de la página de facturas."""

    stats: EstadisticasFacturas
    invoices: list


class ProveedoresPageResponse(BaseModel):
    """Respuesta completa de la página de proveedores."""

    stats: EstadisticasProveedores
    providers: list


class ValidacionesPageResponse(BaseModel):
    """Respuesta completa de la página de validaciones."""

    stats: EstadisticasValidaciones
    rules: list


class RechazosPageResponse(BaseModel):
    """Respuesta completa de la página de rechazos."""

    stats: EstadisticasRechazos
    rejections: list
    causes: list


class LogsPageResponse(BaseModel):
    """Respuesta completa de la página de logs."""

    stats: ConteoLogs
    logs: list


class ControlRegistro(BaseModel):
    """Registro individual de control de factura."""

    id_control: int
    fecha_admision_proveedor: str
    medio_recepcion: str
    fecha_entrega_contabilidad: str
    nombre_recibe_contabilidad: str
    nit_proveedor: str
    nombre_proveedor: str
    numero_factura: str
    forma_pago: str
    acuso_recibido: bool
    recibido_bien_servicio: bool
    aceptacion_expresa: bool
    observaciones_entrega: str


class ControlUpdateRequest(BaseModel):
    """Petición de actualización de un registro de control."""

    fecha_entrega_contabilidad: str | None = None
    nombre_recibe_contabilidad: str | None = None
    forma_pago: str | None = None
    acuso_recibido: bool = False
    recibido_bien_servicio: bool = False
    aceptacion_expresa: bool = False
    observaciones_entrega: str | None = None


class ControlPageResponse(BaseModel):
    """Respuesta paginada de la página de control."""

    items: list
    pagination: dict
