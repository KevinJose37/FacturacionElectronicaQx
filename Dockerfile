# -- Etapa de Construcción --
FROM ghcr.io/astral-sh/uv:python3.12-alpine AS builder

# Configuración de uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app

# Instalar dependencias primero (cache de capas de Docker)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Añadir el código fuente
ADD . /app

# Sincronizar el proyecto
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# -- Etapa Final --
FROM python:3.12-alpine

WORKDIR /app

# Copiar el entorno virtual y el código desde la etapa builder
COPY --from=builder /app /app

# Asegurarse de usar el venv por defecto
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Puerto en el que corre FastAPI
EXPOSE 8888

# Comando para iniciar la aplicación (vía main.py que inicia uvicorn)
CMD ["python", "main.py"]
