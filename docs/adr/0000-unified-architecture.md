# ADR-0000: Unified monorepo, shared core, Hybrid infra

- **Status:** Accepted
- **Date:** 2026-05-27
- **Context:** Two product concerns share most of their plumbing — an
  observability surface (LLM inference logging & ingestion) and an evaluation
  surface (dual-model safety scoring). We build both as one project with two
  separable modules, reusing as much as honestly possible.

## Decision

A single monorepo with a shared Python core and two product modules:

```
platform/
├── core/         llmcore — provider router, memory, tools, pricing  (shared)
├── beacon/       observability: SDK → ingestion → bus → worker → Postgres
├── underwriter/  evaluation: prompt suites → judges → scorecard → report
├── web/          React (Vite) SPA: Chat · Observability · Evaluation
└── deploy/       docker-compose (Hybrid infra), k8s manifests
```

### Key choices

1. **Monorepo + shared `llmcore`.** The chatbot, multi-provider routing, and
   cost model are needed by *both* modules. Defining them once (in `core/`)
   keeps the comparison and the instrumentation consistent. uv workspace installs
   the core editable into one venv. To ship either module on its own, the core is
   small enough to vendor in.

2. **OpenRouter as the provider gateway.** One key reaches GPT-4.1, Claude,
   Gemini, DeepSeek, Grok — all OpenAI-compatible. This gives Beacon true
   multi-provider coverage with one integration and gives Underwriter the
   frontier models to compare. The open-source side (Qwen2.5-3B, self-hosted on
   an HF ZeroGPU Space) is the second gateway. `provider` is recorded per call
   for cost and dashboards.

3. **Hybrid data/event infra (Redpanda + Postgres).** Keep a *real* event bus —
   the SDK returns immediately, ingestion produces to Redpanda and `202`s, a
   worker persists — so observability never sits on the chat's critical path and
   the system stays high-throughput. But consolidate on **one store (Postgres)**
   for both transactional chat state and analytics (indexed rollup views),
   rather than adding a separate OLAP store. Rationale: effort is split across two
   equally-weighted modules; Postgres handles current volumes comfortably and
   halves the ops surface. Dashboards render in-app (React) reading a Postgres
   read API. *(ClickHouse remains the documented scale-out path; see Beacon ADRs.)*

4. **React (Vite) + FastAPI.** Vite SPA for Chat + Observability + Evaluation
   views; FastAPI (SSE, Pydantic) for the gateway, ingestion, and read APIs —
   one backend language across services, the right fit for the LLM-infra
   ecosystem.

5. **PII redaction at the SDK, before egress.** Redaction runs in-process before
   anything is buffered or transmitted; raw PII never reaches the store. Privacy
   by construction.

## Consequences

- More moving parts than a single process — justified by the event-based design
  and the near-real-time dashboards; contained by one-command compose.
- A `request_id` idempotency key threads SDK → ingestion → worker → store to keep
  at-least-once delivery safe.
- Two modules share `llmcore`; splitting for separate submission means vendoring
  `core/` into the chosen module (documented, low-cost).

## Alternatives considered

- **Two unrelated repos.** Simplest mentally, but duplicates the chatbot, cost
  model, and routing, and loses the coherent "instrument + evaluate" story.
- **Full OLAP stack (ClickHouse + Grafana).** Maximum ops-maturity signal, but a
  time sink with a second module to finish; kept as the documented scale path.
- **Single FastAPI app writing straight to Postgres.** Drops the event-based
  design and the scaling story; rejected.
