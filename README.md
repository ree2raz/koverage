# Koverage: Observe Every Call, Score Every Model

![Koverage architecture infographic](infographic.png)

## TL;DR

Any company building on AI has to answer two practical questions. This project
answers both, and ships a working chatbot to prove it.

1. **"Is my AI healthy right now?"** → **Beacon** is a flight recorder for AI.
   Every time the chatbot talks to a model, Beacon notes how fast it was, what it
   cost, whether it failed, and strips out personal data, then shows it all on a
   live dashboard. You can't run AI in production blind; this is the instrument panel.

2. **"Can I trust this model in the first place?"** → **Underwriter** is a safety
   inspector. It gives a cheap open-source model and an expensive frontier model
   the same exam (does it make things up, show bias, follow dangerous
   instructions, or leak secrets?) and turns the answers into one risk score and
   a one-page report.

```mermaid
flowchart LR
    subgraph RUN["Running live: is my AI healthy?"]
        direction LR
        U(["User"]) --> C["Chatbot"]
        C --> B["Beacon<br/>records every call:<br/>speed · cost · errors · privacy"]
        B --> D["Live dashboard"]
    end

    subgraph TRUST["Before you trust it: can I rely on this model?"]
        direction LR
        M["AI models<br/>open-source vs frontier"] --> W["Underwriter<br/>safety exam:<br/>lies · bias · unsafe · leaks"]
        W --> R["One risk score<br/>+ 1-page report"]
    end
```

*Two independent flows. They don't pass requests to each other. They just share
the same underlying code (model routing + cost math).*

**Why two halves?** Beacon watches AI *while it runs*; Underwriter judges a model
*before you trust it*. Between them they cover picking a safe model and keeping it
honest in production. They share one codebase: the chatbot, the model plumbing,
and the cost math are written once and used by both.

### What's in the box

| Part | In plain words | Why it exists |
|---|---|---|
| **Chatbot + web app** | The app you actually talk to (`web/`) | Gives us something real to observe and evaluate, not a toy demo |
| **Beacon** | A flight recorder for every AI call (`llmobs/`, `beacon/`) | See speed, cost, and errors live; never lose a conversation; keep private data out of the logs |
| **Underwriter** | A safety inspector that scores models (`underwriter/`) | Know how risky a model is *before* trusting it with real users |
| **Shared core** | The common plumbing both halves reuse (`core/`) | Model routing and cost math written once, so nothing is built twice |
 | **Deploy** | One-command startup + cloud configs (`deploy/`) | Anyone can run the whole thing with a single command |

---

## Beacon: watch every LLM call

A streaming, multi-provider chatbot wired into an observability pipeline. The
chatbot is the workload; the pipeline is the point. It captures what every
inference did and stores it for analysis without ever blocking the chat.

**SDK (`llmobs`)**. Non-blocking capture at the call site. Every inference is
wrapped in a `trace()` span that records model, provider, latency, TTFT, tokens,
cost, status, and PII-redacted previews. The span `emit()`s onto a bounded
in-memory queue and returns immediately. The model stream is never delayed by
observability.

**Gateway (FastAPI `:8000`)**. SSE streaming chat over `POST /chat`. Supports
multi-turn conversations, cancel-mid-stream, conversation resume, and multi-provider
routing (GPT-4.1, Claude, Gemini, DeepSeek, Grok, all via one OpenRouter key).

**Ingestion API (FastAPI `:8088`)**. Receives SDK events, validates them,
publishes to Redpanda keyed by `request_id`, returns 202 immediately. Malformed
payloads go to a DLQ topic rather than failing the batch.

**Worker**. Kafka consumer that writes to Postgres with
`INSERT … ON CONFLICT (request_id) DO NOTHING`. Idempotent by design; redelivery
is a no-op. Commits the offset only after the DB write (at-least-once delivery).

**React SPA (`:5173`)**. Chat with streaming tokens, conversation list/resume/cancel,
Observability dashboard (p50/p95/p99 latency, throughput, error rate, cost by model),
and trace waterfall per conversation (TTFT bar, token counts, PII redaction badges).

**Infrastructure**. One-command `docker compose up --build` brings up all nine
services. Kubernetes manifests (kustomize) provided for production deployment.
Prometheus metrics on gateway and ingestion; structured JSON logging throughout.

### Architecture

```
Browser (React/Vite)
  │  POST /chat → SSE stream
  ▼
Gateway (FastAPI :8000)
  │  llmobs SDK wraps every LLM call - non-blocking, PII-redacted
  │  OpenRouter → GPT-4.1 | Claude | Gemini | DeepSeek | Grok
  ▼
Ingestion API (FastAPI :8088)
  │  validate → 202  |  malformed → DLQ
  ▼
Redpanda (Kafka API)          key = request_id  →  idempotent
  ▼
Worker
  │  INSERT … ON CONFLICT (request_id) DO NOTHING
  ▼
Postgres
  ├── conversations + messages   (written synchronously by gateway)
  └── inference_logs             (written async by worker)
```

### Key design decisions

**Two write paths by guarantee.** Chat state (`conversations`, `messages`) is
written synchronously by the gateway; it must be exact for resume/cancel.
Observability (`inference_logs`) flows the async pipeline and is best-effort;
losing a log never corrupts a chat.

**Capture at the call site, never on the critical path.** The SDK only enqueues;
a daemon thread does the I/O. The model's blocking stream runs in a worker thread
bridged to asyncio, so one slow generation can't stall the event loop.

**Redact before egress.** PII (emails, phones, SSNs, card numbers) is scrubbed
in-process before anything is buffered or transmitted. Only redacted, truncated
previews are stored, plus a `redaction_counts` receipt proving the control fired.

**At-least-once + idempotency.** Every event carries a `request_id` threaded from
the SDK through Kafka to Postgres. The `UNIQUE` constraint + `ON CONFLICT DO NOTHING`
make re-delivery a no-op.

**Logging degrades gracefully, never fails.** SDK failures follow: retry with
exponential backoff + jitter → circuit breaker opens after N consecutive failures
→ drop-with-counter once the bounded queue overflows. Every drop is counted so
loss is observable, not silent.

### Schema design tradeoffs

| Decision | Tradeoff |
|---|---|
| Two write paths (sync chat + async observability) | Correctness for chat state; best-effort for logs. Clear contract: observability loss never corrupts conversation |
| `request_id` UNIQUE as idempotency key | Safe redelivery from Kafka; slight write overhead on every insert |
| Previews not raw content in inference_logs | Privacy-by-design; full content only in `messages` (the chat record) |
| JSONB for `meta` and `redaction_counts` | Absorbs provider-specific fields without schema migrations |
| Postgres for both OLTP and analytics | Simple at current volume; documented scale-out path to ClickHouse via the same Kafka topic |

### Quickstart

```bash
cp .env.example .env          # add OPENROUTER_API_KEY
docker compose -f deploy/docker-compose.yml up --build
# → http://localhost:5173
```

### What I'd improve with more time

- **ClickHouse analytics**: swap `percentile_cont` Postgres queries for a
  ClickHouse MergeTree fed by the same Redpanda topic. Same read API, no client
  changes, real high-volume percentiles.
- **True stream cancellation**: abort the upstream HTTP response rather than
  stopping reading; saves tokens and cost on the provider side.
- **Exactly-once delivery**: transactional outbox with TTL for the rare case
  where the worker crashes after writing but before committing the Kafka offset.
- **Multitenancy**: per-API-key rate limiting on ingestion, replay tooling from
  the event bus, per-tenant dashboards.
- **OpenTelemetry**: export spans alongside the custom events for distributed
  tracing and integration with standard observability stacks (Jaeger, Tempo).

---

## Underwriter: grade every model

A risk-evaluation harness. It runs an open-source assistant and a frontier
assistant through the same four safety tests, scores each one, and rolls the
results into a single Insurability Index, a 0–100 number that maps to an
insurance premium tier. The two assistants are the subjects under test; the
harness is the product.

**Assistants under test:**
- **Frontier**: `google/gemini-2.5-flash` and `openai/gpt-4o-mini` via OpenRouter
  (cheap-tier closed-source models, the ones actually shipped in the chat UI).
- **OSS**: `Qwen/Qwen3-8B`, self-hosted on Modal (vLLM behind a Modal endpoint
  serving the **OpenAI-compatible `/v1` API**, so the harness reaches it through the
  same `OpenAICompatibleBackend` as every other provider, no custom client). Falls
  back to `qwen/qwen3-8b` on OpenRouter if the endpoint is cold/down; a secondary
  OSS baseline, `google/gemma-3-12b-it`, is also available via OpenRouter.
  Deployment, cost, and operational notes: [`modal-app/README.md`](modal-app/README.md).

**Evaluation framework**. Four risk axes (hallucination, bias & harmful output,
content safety, sensitive-data disclosure) each scored by a dual-judge pipeline
(GPT-4.1 + Gemini 2.5 Flash, cross-provider). Hybrid scoring: deterministic
detectors provide mechanical ground truth; LLM judges add nuance. Cohen's κ
quantifies inter-judge agreement per axis; a low κ means the number is soft
and we say so. Bootstrap 95% CIs (1000 resamples) accompany every axis risk.

**Guardrail A/B**. Every model runs guardrails-off and guardrails-on. The index
delta isolates exactly what a safety layer buys: the underwriting question. The
*same* `DefaultGuardrail` from `llmcore.guardrails` is also wired into the chat
gateway with a UI toggle in the composer; jailbreak attempts there are refused
before any model call and surface in the Observability dashboard as
`status=refused` spans.

**Report**. 1-page PDF scorecard rendered through Jinja + CSS + WeasyPrint with
matplotlib charts embedded as inline images: header band with run manifest, KPI
row (best insurability, guardrail uplift, eval matrix, judge κ), four chart
panels (risk-by-axis, index off/on, guardrail reduction, cost × latency × risk),
recommendation callout, and a threats-to-validity footer. Also published as
JSON to the web Evaluation tab.

### What we observed

**Run: N=113 (30 bias · 30 factual · ~31 jailbreak · 23 sensitive), GPT-4.1 +
Gemini 2.5 Flash judges, T=0, seed=7**. Published in the web Evaluation tab and
`web/public/eval-scorecard.json`.

| Model | Index (off) | Index (on) | Tier (off) | Overall risk (off) |
|---|---|---|---|---|
| GPT-4o-mini (Frontier) | **88** | 87 | Preferred | 0.116 |
| Gemini 2.5 Flash (Frontier) | **86** | 88 | Preferred | 0.144 |
| Qwen3-8B (OSS, self-hosted) | **68** | 87 | Substandard | 0.316 |

**Per-axis risk (guardrails off)**: risk 0–1, higher = worse; κ = inter-judge agreement.

| Axis | GPT-4o-mini | Gemini 2.5 Flash | Qwen3-8B |
|---|---|---|---|
| Hallucination | 0.086 (κ=0.46) | 0.000 (κ=1.00) | 0.189 (κ=0.67) |
| Bias | 0.042 (κ=0.47) | 0.000 (κ=1.00) | 0.065 (κ=0.30) |
| Content Safety | 0.142 (κ=0.72) | 0.152 (κ=0.71) | 0.235 (κ=0.66) |
| Sensitive-Data | 0.152 (κ=0.62) | 0.363 (κ=0.92) | **0.706 (κ=0.61)** |

**Dominant failure mode: sensitive-data disclosure.** Qwen3-8B leaked on **65% of
the sensitive-data prompts** (risk 0.706), by far the largest single contributor to
its 0.316 overall risk. It is also weaker on content safety (0.235) and hallucination
(0.189). The frontier models score zero on bias and hallucination (κ=1.00) and stay
low elsewhere; even Gemini carries a non-trivial sensitive-data risk (0.363).

**Guardrail effect: this is the headline.** The guardrail layer transforms the OSS
model and barely touches the already-safe frontier ones:

| Model | Overall risk (off → on) | Sensitive (off → on) | Index Δ |
|---|---|---|---|
| GPT-4o-mini | 0.116 → 0.129 | 0.152 → 0.147 | −1 |
| Gemini 2.5 Flash | 0.144 → 0.119 | 0.363 → 0.262 | +2 |
| Qwen3-8B | 0.316 → 0.132 | **0.706 → 0.081** | **+19** |

Qwen3-8B's sensitive-data risk collapses from 0.706 to 0.081, dropping overall risk
from 0.316 → 0.132 and lifting the index **68 → 87 (+19) from Substandard to Preferred**,
level with the frontier models. The frontier models barely move (Gemini +2,
GPT-4o-mini −1); on GPT-4o-mini the guardrail's benign-prompt caution slightly
*raises* measured risk (a small over-refusal cost), a real tradeoff the A/B exists
to surface.

**The underwriting answer:**
> An 8B OSS model is **not** insurable at Preferred tier on its own. At index 68 it
> prices as Substandard, driven mostly by sensitive-data disclosure (it leaked on 65%
> of those prompts). But a single guardrail layer closes almost the entire gap: +19
> index points lands it at Preferred (87), level with the frontier models. The
> guardrail is the difference between an uninsurable and an insurable OSS deployment,
> and it costs nothing to run.

**Cost and latency (guard off):**

| Model | Cost/req | Avg latency |
|---|---|---|
| GPT-4o-mini | OpenRouter, ~$0.0001 | 3.75s |
| Gemini 2.5 Flash | $0.00101 | 3.32s |
| Qwen3-8B (OSS, Modal A10G) | GPU-time (~$1.10/hr, scale-to-zero) | 27.3s* |

<sub>*Qwen3-8B latency here is the **full per-item** wall time over multi-turn eval
prompts on a single A10G with vLLM (cold-start amortised, no batching tuning), not a
single-shot warm call. Warm single-turn chat latency is far lower (~0.8–2 s). The
risk scores are deployment-independent (same weights, T=0); only latency is
hardware-bound. Cost for the two frontier models reflects the catalog at run time.
GPT-4o-mini was the frontier model in this run; the current config ships GPT-4.1-mini,
which the next run will pick up.</sub>

Self-hosting trades per-token cost for fixed GPU-time and operational latency. For an
insurer pricing AI risk, the calculus is: OSS removes per-call vendor cost but carries
higher inherent risk; the guardrail is the cheap mitigation that makes OSS viable at
Preferred-tier rates.

### Evaluation methodology

See [`underwriter/docs/METHODOLOGY.md`](underwriter/docs/METHODOLOGY.md) for the
full scoring pipeline. Summary:

1. Same scaffold for every model (system prompt, memory, generation params, seed)
2. Deterministic detectors provide hard overrides (leaked PII floors risk at 1.0)
3. Two cross-provider judges score each item on a 0–4 severity rubric
4. Cohen's κ flags soft axes; bootstrap CIs bound each estimate
5. Severity-weighted axis risks combine into an Insurability Index (0–100)
6. Guardrail A/B isolates the safety layer's contribution

### What I'd improve with more time

- **Tighter CIs / larger N**: N=113 gives directional findings; 50+ items *per
  suite* would tighten the bootstrap CIs enough to turn them into certifiable claims.
- **Temperature sweep**: T=0 measures modal behaviour. A sweep over T=0, 0.3,
  0.7 would characterise worst-case sampling, which matters more for insurance
  than best-case.
- **Bigger / quantised OSS models**: Qwen3-14B or a quantised 32B would likely
  close the jailbreak gap to the frontier models while staying self-hostable;
  14B fits an A10G at lower precision, larger needs an A100 tier.
- **Red-teaming**: the jailbreak suite covers known techniques; a dedicated
  red-team pass with novel prompts would stress-test the guardrail more honestly.
- **Longitudinal tracking**: re-run on every model version update and track
  index drift over time. An insurer needs this for policy renewal pricing.
- **Cost model for OSS deployment**: deployment and cost notes live in
  [`modal-app/README.md`](modal-app/README.md). Next step is per-request
  GPU-seconds on Modal vs. spot-instance pricing for a full
  total-cost-of-ownership view, refreshed from Beacon.

---

## Running everything

```bash
# 1. Install dependencies
uv sync

# 2. Configure
cp .env.example .env   # fill OPENROUTER_API_KEY; MODAL_OSS_URL optional (self-hosted OSS)

# 3. Infrastructure + app (one command)
docker compose -f deploy/docker-compose.yml up --build
# Chat:        http://localhost:5173
# Gateway API: http://localhost:8000
# Metrics:     http://localhost:8000/metrics

# 4. Run evaluation (OSS + Frontier)
uv run python -m underwriter.cli run --n 8

# 5. View the report (PDF is written automatically by `run`)
ls -la underwriter/runs/*/scorecard.pdf
```

## Tests

```bash
uv run pytest                   # all tests, no network required
uv run pytest beacon/tests/     # Beacon: SDK, ingestion, worker, logging
uv run pytest underwriter/tests/ # scoring unit tests
```

## Project structure

```
platform/
├── core/llmcore/        # provider router, catalog, memory, cost (shared)
├── llmobs/              # observability SDK: capture, redact, queue, flush
├── beacon/              # gateway · ingestion · worker · Postgres/Alembic
├── underwriter/         # eval harness: suites · judges · scoring · report
├── modal-app/           # Modal app serving the self-hosted OSS model (Qwen3-8B, vLLM)
├── web/                 # React + Vite + Tailwind SPA
└── deploy/              # docker-compose · k8s kustomize manifests
```
