# syntax=docker/dockerfile:1.7
# Imagen multi-stage: builder + runtime mínima.
# Optimizado para tamaño y para que el grafo OSM se monte como volumen, no se incluya en la imagen.

# ===== Builder =====
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=0

# uv para instalar dependencias rápido
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /bin/

# Dependencias del sistema necesarias para OSMnx/Shapely (GEOS, GDAL via wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar deps primero (cache layer)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project --no-dev || uv sync --no-install-project --no-dev

# Copiar código
COPY src ./src
COPY README.md LICENSE ./

# Instalar el package
RUN uv sync --frozen --no-dev || uv sync --no-dev

# ===== Runtime =====
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Runtime mínimo (sin compilers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgeos-c1v5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --shell /bin/bash app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src

USER app

# El grafo OSM y la BD vienen por volumen (ver docker-compose.yml)
VOLUME ["/app/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "sentinel_dispatch.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
