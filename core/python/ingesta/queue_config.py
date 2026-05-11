"""Configuración para el worker de cola de trabajo."""

from config import get_config, load_yaml_config

_settings = load_yaml_config('settings.yaml')
_queue_worker_cfg = _settings.get('queue_worker', {})


class QueueWorkerConfig:
    """Metadatos y configuración del worker de colas."""

    poll_interval_seconds: int = int(_queue_worker_cfg.get('poll_interval_seconds', 5))
    """Intervalo de polling cuando no hay trabajo disponible y falla LISTEN."""

    max_backoff_seconds: int = int(_queue_worker_cfg.get('max_backoff_seconds', 60))
    """Máximo backoff exponencial entre polls."""

    stuck_job_timeout_minutes: int = int(_queue_worker_cfg.get('stuck_job_timeout_minutes', 10))
    """Tiempo máximo que un job puede estar EN_PROCESO antes de considerarse atascado."""

    batch_size: int = int(_queue_worker_cfg.get('batch_size', 10))
    """Número máximo de eventos a reclamar por iteración del worker."""

    max_reintentos: int = int(_queue_worker_cfg.get('max_reintentos', 3))
    """Máximo número de reintentos permitidos antes de marcar como FALLIDO."""
