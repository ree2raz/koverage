# syntax=docker/dockerfile:1
# Ollive platform — Python services (gateway, ingestion, worker).
# Build context: platform/ (workspace root)
# Override CMD per service in docker-compose.yml.
#
# Cache strategy:
#   --mount=type=cache preserves uv's HTTP/wheel cache across builds so
#   packages are downloaded once and reused. uv sync is still re-run on
#   source changes but resolves instantly from cache (no network round-trips).
#   Full source must be present before uv sync for editable workspace installs.

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy entire workspace — editable installs require source present at sync time
COPY pyproject.toml uv.lock ./
COPY core/ core/
COPY llmobs/ llmobs/
COPY beacon/ beacon/
COPY underwriter/ underwriter/

# Install dependencies — uv cache persists across builds via BuildKit mount
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "beacon.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
