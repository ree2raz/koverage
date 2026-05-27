# Ollive Platform — observe and judge every LLM call

Two Ollive take-homes, one coherent product. A single multi-provider chatbot
sits on a shared LLM core; every inference it makes is **observed** and
**evaluated**.

| Module | Assignment | What it does |
| --- | --- | --- |
| **Beacon** (`beacon/`) | Founding Fullstack Engineer | Drop-in LLM **observability**: an SDK captures inference metadata (latency, TTFT, tokens, cost, status, PII-redacted previews) → event bus → store → live dashboards. |
| **Underwriter** (`underwriter/`) | Founding AI/ML Engineer | LLM **evaluation**: scores models on hallucination, bias & harmful output, and content safety → an insurability scorecard with cost × latency × risk tradeoffs. |
| **core** (`core/`) | shared | `llmcore`: provider router (OpenRouter → GPT-4.1, Claude, Gemini, DeepSeek, Grok), memory, tools, pricing/cost. Both modules build on it. |

Each module is independently submittable; they share `llmcore` so the chatbot,
cost model, and provider routing are defined exactly once.

> Why this shape for **Ollive** (AI liability insurance): an insurer needs to
> *instrument* AI in production (Beacon → incident response, monitoring) and
> *quantify its risk* (Underwriter → hallucination / bias / safety). This
> project is both halves of that on one stack.

## Architecture (at a glance)

```
React (Vite) web  ──SSE──▶  Chat gateway (FastAPI)  ──[llmobs SDK]──▶  Ingestion API ──▶ Redpanda ──▶ Worker ──▶ Postgres
  Chat · Observability        multi-provider router      capture + PII redact      validate, 202 fast        idempotent     (chat state +
  · Evaluation                (OpenRouter)                async, non-blocking                                  upsert        rollup views)
                                    │
                                    └────────────  Underwriter eval harness drives the same core → scorecard + report
```

Decisions are recorded in [`docs/adr/`](docs/adr/). Beacon's deeper notes live
in [`beacon/docs/`](beacon/docs/); Underwriter's in [`underwriter/docs/`](underwriter/docs/).

## Quickstart

```bash
# 1. Python workspace (shared core + both modules)
uv sync                         # creates .venv, installs llmcore editable
cp .env.example .env            # add OPENROUTER_API_KEY (+ GEMINI_API_KEY for judges)
uv run pytest                   # core tests, no network required

# 2. Infrastructure (Postgres + Redpanda event bus)
docker compose -f deploy/docker-compose.yml up -d
```

Per-module run instructions land in `beacon/README.md` and
`underwriter/README.md` as those phases complete.

## Status

- [x] **Phase 0** — monorepo, shared `llmcore` (router, memory, tools, pricing), compose infra
- [x] **Phase 1** — Beacon core: llmobs SDK + gateway (SSE, multi-provider, cancel) + ingestion + worker + Postgres/Alembic
- [ ] **Phase 2** — React web app: Chat · Observability · Evaluation
- [ ] **Phase 3** — Underwriter eval module + scorecard + report
- [ ] **Phase 4** — deploy (compose one-command, k3d) + hardening + tests
- [ ] **Phase 5** — docs + demo + submission
