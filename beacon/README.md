# Beacon — drop-in LLM observability

Capture inference metadata (latency, **TTFT**, tokens, cost, status, PII-redacted
previews) from any LLM call, ship it without ever blocking the call, and view it
on live dashboards and a per-conversation trace.

Architecture notes (ingestion flow, logging strategy, scaling, failure handling,
schema decisions): [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Components
| Path | What |
| --- | --- |
| `llmobs/` | The SDK: `trace()` span → capture + **redact PII before egress** → bounded async queue → batched POST. Non-blocking, retry, circuit breaker, drop-with-counter. |
| `beacon/gateway/` | FastAPI chat: SSE streaming, multi-provider, conversation persistence, cancel; read API for dashboards. |
| `beacon/ingestion/` | FastAPI: validate + `x-api-key`, produce to Redpanda, return `202`; bad events → DLQ. |
| `beacon/worker/` | Redpanda consumer → idempotent upsert into Postgres; poison → DLQ. |
| `beacon/db/` | SQLAlchemy models + Alembic migrations. |

## Run it locally

From the repo root (`platform/`):

```bash
uv sync
cp .env.example .env          # set OPENROUTER_API_KEY (chat); INGEST_API_KEY defaults are fine

# 1. infra: Postgres + Redpanda
docker compose -f deploy/docker-compose.yml up -d

# 2. schema
cd beacon && uv run alembic upgrade head && cd ..
#   (or the dev shortcut:  uv run python -m beacon.db.init)

# 3. the three services, each in its own terminal
uv run uvicorn beacon.ingestion.main:app --port 8088
uv run python -m beacon.worker.main
uv run uvicorn beacon.gateway.main:app --port 8000
```

### Smoke test — watch a redacted log land end-to-end
```bash
# stream a chat turn (SSE)
curl -N -X POST localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message":"hi, email me at jane@example.com","model":"openai/gpt-4.1"}'

# the inference log (note the redacted preview + redaction_counts)
curl -s localhost:8000/api/logs | jq '.[0] | {provider,model,latency_ms,ttft_ms,cost_usd,input_preview,redaction_counts}'

# aggregate metrics for the dashboards
curl -s localhost:8000/api/metrics/summary | jq
```

## Offline tests (no infra, no keys)
```bash
uv run pytest beacon/tests
```
Covers the redaction golden set, the SDK's non-blocking / retry / circuit-breaker /
bounded-drop behaviour, and the tracer's event construction.

## Endpoints
- `POST /chat` — SSE token stream (`meta` → `token`… → `done`).
- `POST /conversations/{id}/cancel` — stop an in-flight stream.
- `GET /models` — model catalog for the selector.
- `GET /api/conversations`, `/api/conversations/{id}`, `/api/conversations/{id}/logs`
- `GET /api/logs`, `/api/metrics/summary`, `/api/metrics/timeseries`
- `GET /healthz`, `/readyz`, `/metrics` (Prometheus)
