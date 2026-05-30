# Beacon — Architecture Notes

Beacon is a drop-in LLM observability pipeline: an SDK captures inference
metadata at the call site, ships it without blocking the caller, and an
event-driven pipeline validates, fans out, and persists it for dashboards and
trace inspection.

```
React (Vite)            Chat gateway (FastAPI)            Ingestion (FastAPI)         Worker
 Chat · Dashboards  ──▶  /chat  SSE stream         ──▶    POST /v1/ingest      ──▶    consumer group
 list/resume/cancel      multi-provider (OpenRouter)      validate + x-api-key        idempotent upsert
        ▲                instrumented by llmobs SDK ──┐   produce → Redpanda, 202     poison → DLQ
        │ read API                                    │            │                       │
        └──────────────  /api/metrics, /api/logs  ◀───┴── Postgres ◀── inference_logs ◀─────┘
                                                          conversations + messages
                                                          (written synchronously by the gateway)
```

## Ingestion flow

1. The **gateway** makes an LLM call; the **llmobs SDK** wraps it in a `trace()` span.
2. The span captures metadata — model, provider, latency, **TTFT**, tokens, cost,
   status — **redacts PII in-process**, builds previews, and `emit()`s the event
   onto a bounded in-memory queue. `emit()` returns immediately.
3. A background flusher batches events and `POST`s them to the **ingestion API**.
4. Ingestion authenticates (`x-api-key`), validates each event (Pydantic), and
   **produces to Redpanda** keyed by `request_id`, returning **202** at once.
   Unparseable events are routed to a **DLQ** rather than failing the batch.
5. The **worker** consumes the topic, sets `ingested_at`, and writes to Postgres
   with `INSERT … ON CONFLICT (request_id) DO NOTHING`. Commits the Kafka offset
   only **after** the DB write (at-least-once). Poison messages → DLQ.

Chat state (`conversations`, `messages`) is written **synchronously by the
gateway** — it must be exact for resume/cancel. Observability (`inference_logs`)
flows the async path and is best-effort; losing a log never corrupts a chat.

## Logging strategy

- **Capture at the call site, never on the critical path.** The SDK only enqueues;
  a daemon thread does the I/O. The model's blocking stream itself runs in a worker
  thread bridged to async, so one slow generation can't stall the event loop.
- **Redact before egress.** PII is scrubbed in-process before anything is buffered
  or transmitted; only redacted, truncated previews are stored, plus a
  `redaction_counts` receipt proving the control fired.
- **At-least-once + idempotency.** Every event carries a `request_id`; the unique
  constraint + `ON CONFLICT DO NOTHING` make re-delivery a no-op.
- **Head-based sampling** (`sample_rate`) for volume control.

## Scaling considerations

- **Stateless gateway and ingestion** scale horizontally; the event bus absorbs
  bursts so ingestion latency stays flat under load.
- **Redpanda partitions + consumer groups** scale the worker; `request_id` keying
  preserves per-request ordering and dedupe locality.
- **Postgres** serves both transactional chat state and analytics here. Analytics
  queries use `percentile_cont` + `date_trunc` rollups; indexes on
  `(ts, provider, model)` keep them cheap at current volume. **Scale-out path:**
  swap the analytics reads for a ClickHouse `MergeTree` fed by the same topic
  (Kafka-engine table → materialized rollups) behind the identical read API —
  documented as the next step rather than built, to keep the surface honest.
- **Bounded SDK queue + sampling** cap the client-side memory and egress cost.

## Failure-handling assumptions

- **Logging must never break or slow chat.** SDK failures degrade: retry with
  exponential backoff + jitter → **circuit breaker** opens after N consecutive
  failures → **drop-with-counter** once the bounded queue overflows. Every drop is
  counted (`dropped_overflow` / `dropped_breaker` / `dropped_failed`) so loss is
  observable, not silent.
- **Ingestion outage** → SDK retries, then sheds load; chat is unaffected.
- **Worker crash** → uncommitted offsets are re-delivered on restart; idempotent
  writes make redelivery safe.
- **Poison messages** → DLQ, so one bad record never wedges the consumer group.
- **Cancellation** → the gateway stops streaming, persists the partial answer, and
  the span records `status=cancelled`.

## Schema design decisions

- **Two write paths by guarantee** (synchronous chat state vs async observability) —
  the core tradeoff, made explicit.
- **Previews, not raw content.** The observability path stores only redacted,
  truncated previews; full content lives only in `messages` (the chat record).
- **Deleting a chat does not erase its observability.** `DELETE /api/conversations/{id}`
  removes the conversation and its `messages` (the chat record, cascade), but
  **leaves `inference_logs` intact**. This is deliberate: the two write paths have
  different lifecycles. Chat state is user-owned and disposable; `inference_logs`
  is an *append-only operational audit stream* — latency, cost, error, and PII-control
  receipts that ops and finance rely on. If deleting a chat retroactively erased its
  logs, historical dashboards (p95 latency, cost-by-model, error rate for a past
  window) would silently change every time a user pruned history, which defeats the
  purpose of an audit trail. The logs already hold no raw content — only redacted
  previews — so retention is privacy-safe. The cost is a dangling
  `inference_logs.conversation_id` whose trace view 404s; `conversation_id` is
  therefore an intentionally *soft* reference, not a foreign key. For a strict
  right-to-erasure requirement the documented next step is a soft-delete that nulls
  `conversation_id` and the previews while preserving the numeric metrics.
- **`request_id` UNIQUE** is the idempotency key threaded end-to-end.
- **JSONB escape hatches** (`meta`, `redaction_counts`) absorb provider-specific
  fields without migrations.
- **Numeric(12,6) cost** avoids float drift on money.
- Migrations via **Alembic** (`alembic upgrade head`).

## What we observed in production

Running the full stack end-to-end hit a few things worth writing down:

**Postgres NUMERIC → JSON string bug.** `psycopg3` returns `decimal.Decimal` for
`NUMERIC` columns; FastAPI's default JSON encoder serializes these as strings, not
numbers. TypeScript received `"0.00420"` and `.toFixed()` threw at runtime, blanking
the UI. Fixed in `read.py` with a `_coerce()` helper that converts `Decimal → float`
before serialization. Lesson: test the full round-trip to the UI, not just
the SQL query.

**SSE silent failure on DB errors.** If the database was unavailable, `chat_stream`
raised before its first `yield`, producing an HTTP 200 with an empty body. The
browser's `EventSource` saw no events and no error — the UI just hung silently.
Fixed by wrapping the entire generator body in `try/except` that yields an `error`
SSE frame. Lesson: async generators need top-level error handling; exceptions before
the first yield are invisible to the consumer.

**Environment variables not reaching Docker containers.** `${VAR:-}` in Compose
reads from the shell environment at parse time, not from `.env`. Secrets in `.env`
were silently empty inside containers. Fixed with `env_file: ../.env` on every
app service, combined with `environment:` overrides for Docker-internal hostnames.
Lesson: `env_file` is the correct pattern for file-based secrets; variable
substitution in Compose is for shell-level overrides only.

**Two-stage Dockerfile broke editable installs.** Copying `site-packages` between
stages fails because `.pth` files for editable installs point to absolute source
paths that don't exist in the second stage. Fixed with a single-stage Dockerfile
using a uv virtualenv and `ENV PATH="/app/.venv/bin:$PATH"`.

## What I'd improve with more time

- ClickHouse analytics path (above) for real high-volume percentiles.
- True stream cancellation (abort the upstream HTTP response, not just stop reading).
- Exactly-once into Postgres via a transactional outbox / dedupe table with TTL.
- Per-API-key multitenancy + rate limiting on ingestion; replay tooling from the bus.
- OpenTelemetry spans alongside the custom events for distributed tracing.
