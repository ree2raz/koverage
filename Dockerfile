# Multi-purpose image for all Beacon Python services.
# Build context: platform/ (workspace root)
# Override CMD per service in docker-compose.yml.
#
# Stages:
#   deps  — install workspace dependencies via uv
#   app   — lean runtime image

FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_SYSTEM_PYTHON=1 UV_NO_CACHE=1 PYTHONDONTWRITEBYTECODE=1

# Copy workspace manifests first (cache-friendly layer)
COPY pyproject.toml uv.lock ./
COPY core/pyproject.toml core/
COPY llmobs/pyproject.toml llmobs/
COPY beacon/pyproject.toml beacon/
COPY underwriter/pyproject.toml underwriter/

RUN uv sync --frozen --no-dev

# ── runtime ─────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS app

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy source (installed editable, so source must be present)
COPY core/ core/
COPY llmobs/ llmobs/
COPY beacon/ beacon/
COPY underwriter/ underwriter/

# Default: gateway (overridden per service in compose)
CMD ["uvicorn", "beacon.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
