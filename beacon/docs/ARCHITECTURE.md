# Beacon — Architecture Notes

Beacon is a drop-in LLM-observability pipeline: an SDK captures inference
metadata at the call site, ships it without blocking the caller, and an
event-driven pipeline validates, fans out, and persists it for dashboards and
trace inspection.

```
React (Vite)            Chat gateway (FastAPI)            Ingestion (FastAPI)         Worker
 Chat · Dashboards  ──▶  /chat  SSE stream         ──▶    POST /v1/ingest      ──▶    consume group
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
   with `INSERT … ON CONFLICT (request_id) DO NOTHING`. It commits the Kafka
   offset only **after** the DB write (at-least-once). Poison messages → DLQ.

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
  `(ts, provider, model)` keep them cheap at take-home volume. **Scale-out path:**
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

## Schema-design decisions
- **Two write paths by guarantee** (synchronous chat state vs async observability),
  as above — the core tradeoff, made explicit.
- **Previews, not raw content.** The observability path stores only redacted,
  truncated previews; full content lives only in `messages` (the chat record).
- **`request_id` UNIQUE** is the idempotency key threaded end-to-end.
- **JSONB escape hatches** (`meta`, `redaction_counts`) absorb provider-specific
  fields without migrations.
- **Numeric(12,6) cost** avoids float drift on money.
- Migrations via **Alembic** (`alembic upgrade head`); `python -m beacon.db.init`
  is the one-step dev shortcut.

## What I'd improve with more time
- ClickHouse analytics path (above) for real high-volume percentiles.
- True stream cancellation (abort the upstream HTTP response, not just stop reading).
- Exactly-once into Postgres via a transactional outbox / dedupe table with TTL.
- Per-API-key multitenancy + rate limiting on ingestion; replay tooling from the bus.
- OpenTelemetry spans alongside the custom events for distributed tracing.
