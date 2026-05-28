# Ollive platform — Python services (gateway, ingestion, worker).
# Build context: platform/ (workspace root)
# Override CMD per service in docker-compose.yml.
#
# uv creates /app/.venv; PATH is extended so uvicorn/alembic are found.

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_NO_CACHE=1

# Copy entire workspace (editable installs need source present at sync time)
COPY pyproject.toml uv.lock ./
COPY core/ core/
COPY llmobs/ llmobs/
COPY beacon/ beacon/
COPY underwriter/ underwriter/

RUN uv sync --frozen --no-dev

# Put the virtualenv's bin dir first so uvicorn/alembic are found
ENV PATH="/app/.venv/bin:$PATH"

# Default entrypoint — overridden per service in docker-compose.yml
CMD ["uvicorn", "beacon.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
