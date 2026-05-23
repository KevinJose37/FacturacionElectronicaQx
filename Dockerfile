# -- Etapa de Construcción --
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

# Configuración de uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Copiar archivos de dependencias
COPY pyproject.toml uv.lock* ./

# Instalar dependencias (regenera lockfile si es necesario)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

# Añadir el código fuente
ADD . /app

# Sincronizar el proyecto
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev


# -- Etapa Final --
FROM python:3.12-alpine

WORKDIR /app

# Instalar dependencias del sistema (libmagic para python-magic, libstdc++ para PyMuPDF, ca-certificates para SSL)
RUN apk add --no-cache libmagic libstdc++ ca-certificates

# Copiar el entorno virtual y el código desde la etapa builder
COPY --from=builder /app /app

# Asegurarse de usar el venv por defecto
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Puerto en el que corre FastAPI
EXPOSE 8888

# Comando para iniciar la aplicación (vía main.py que inicia uvicorn)
CMD ["python", "main.py"]
