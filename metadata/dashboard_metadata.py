"""Metadatos del dashboard y utilidades de presentación temporal.

Definiciones de KPIs, etapas del pipeline y formateo de tiempo relativo
reutilizables por servicios del dashboard y proveedores.
"""


class KpiDefiniciones:
    """Definiciones de los KPIs del dashboard principal."""

    items = (
        {'key': 'processed', 'label': 'Facturas procesadas', 'color': 'turquoise'},
        {'key': 'validated', 'label': 'Facturas validadas', 'color': 'turquoise'},
        {'key': 'rejected', 'label': 'Facturas rechazadas', 'color': 'orange'},
        {'key': 'pending_human', 'label': 'Verificación manual', 'color': 'orange'},
        {'key': 'time', 'label': 'Tiempo promedio', 'color': 'purple'},
        {'key': 'total_value', 'label': 'Valor total facturado', 'color': 'turquoise'},
        {'key': 'providers', 'label': 'Proveedores', 'color': 'turquoise'},
        {'key': 'cuentas_por_pagar', 'label': 'Cuentas por pagar', 'color': 'orange'},
    )
    """Tupla de dicts con key, label y color de cada KPI."""


class EtapasFlujo:
    """Definiciones de las etapas del pipeline de facturación."""

    items = (
        {'id': 'intake', 'label': 'Entrada'},
        {'id': 'validation', 'label': 'Validación'},
        {'id': 'processing', 'label': 'Procesamiento'},
        {'id': 'done', 'label': 'Finalizado'},
    )
    """Tupla de dicts con id y label de cada etapa."""


class DiasNombre:
    """Nombres abreviados de los días de la semana."""

    por_indice = ('Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb')
    """Tupla ordenada por EXTRACT(DOW) de PostgreSQL: 0=Dom..6=Sáb."""


class FormatoTiempo:
    """Utilidades para formatear deltas de tiempo como texto relativo."""

    nunca = 'nunca'
    """Texto cuando no hay fecha de referencia."""

    hace_segundos = 'hace segundos'
    """Texto cuando el delta es menor a 1 minuto."""

    plantilla_minutos = 'hace {valor}m'
    """Plantilla para deltas menores a 1 hora. Acepta .format(valor=...)."""

    plantilla_horas = 'hace {valor}h'
    """Plantilla para deltas menores a 1 día. Acepta .format(valor=...)."""

    plantilla_dias = 'hace {valor}d'
    """Plantilla para deltas de 1 día o más. Acepta .format(valor=...)."""

    @staticmethod
    def desde_minutos(minutos: int) -> str:
        """Convierte un delta en minutos a texto relativo legible.

        Args:
            minutos: Delta de tiempo en minutos.
        """
        if minutos < 1:
            resultado = FormatoTiempo.hace_segundos
        elif minutos < 60:
            resultado = FormatoTiempo.plantilla_minutos.format(valor=minutos)
        elif minutos < 1440:
            resultado = FormatoTiempo.plantilla_horas.format(valor=minutos // 60)
        else:
            resultado = FormatoTiempo.plantilla_dias.format(valor=minutos // 1440)
        return resultado
