# Ollive platform — Python services (gateway, ingestion, worker).
# Build context: platform/ (workspace root)
# Override CMD per service in docker-compose.yml.
#
# Layer order is critical for cache efficiency:
#   1. Copy ONLY manifest files → uv sync (cached until deps change)
#   2. Copy source code         → only this layer rebuilds on .py changes

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── Step 1: dependency install (cached until pyproject.toml / uv.lock change) ──
# Copy only the manifest files needed for uv sync.
# uv editable installs create .pth files pointing to source dirs;
# the source itself is not required at sync time.
COPY pyproject.toml uv.lock ./
COPY core/pyproject.toml core/
COPY llmobs/pyproject.toml llmobs/
COPY beacon/pyproject.toml beacon/
COPY underwriter/pyproject.toml underwriter/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ── Step 2: copy source (only this layer rebuilds on .py changes) ────────────
COPY core/ core/
COPY llmobs/ llmobs/
COPY beacon/ beacon/
COPY underwriter/ underwriter/

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "beacon.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
