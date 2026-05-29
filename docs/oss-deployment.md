# OSS Deployment — Qwen2.5-3B on Hugging Face Spaces

The open-source assistant for the AI/ML evaluation is `Qwen/Qwen2.5-3B-Instruct`
deployed to Hugging Face Spaces on **ZeroGPU**. Same prompts, same eval harness,
same observability as the frontier models — so the comparison is apples-to-apples.

**Live Space:** https://huggingface.co/spaces/ree2raz/da-platform

## Why HF Spaces + ZeroGPU

- **Free GPU access** under HF Pro ($9/mo flat) — no per-second billing while we
  iterate on the eval suite.
- **Persistent model weights** — Qwen2.5-3B (~6 GB fp16) loads once at module
  import and stays resident; only the GPU compute slot is allocated per request.
- **Public inference endpoint** that the harness can hit from anywhere via the
  Gradio client — no VPN, no API gateway, no auth plumbing.

Alternatives we considered: Modal ($1.10/hr A10G, pay-per-second), Replicate
(~$0.00055/s), RunPod (cheaper but no public-endpoint convenience), Ollama
(local only — not a "deploy publicly" answer).

## Files

| Path | What it does |
|---|---|
| `hf-space/app.py` | Gradio entry point, loads Qwen at import, exposes `/eval` |
| `hf-space/requirements.txt` | `gradio`, `transformers`, `accelerate`, `spaces`, `torch` |
| `hf-space/README.md` | HF Space front-matter (sdk, python_version, etc.) |

## Setup (reproducing the deployment)

```bash
# 1. Create a Space (Gradio SDK, ZeroGPU hardware) on huggingface.co/new-space
# 2. Clone, copy the contents of platform/hf-space/ into the Space repo
# 3. git push — HF builds the image and starts the Space (~5 min first time)

# To point the local eval harness at the Space:
echo 'OSS_SPACE_URL=https://<your-user>-<space-name>.hf.space' >> platform/.env
```

The `/eval` API is the only contract the harness depends on:

```python
from gradio_client import Client
client = Client("ree2raz/da-platform")
result = client.predict(prompt, system_prompt, api_name="/eval")
# → {"text": "...", "latency_s": 2.15, "completion_tokens": 87}
```

## Cost + Latency (representative)

Numbers below are the **mean per-request** values captured by Beacon during the
2026-05-28 full eval run (n=32 prompts per model, no guardrail). Re-run the SQL
in the next section after a fresh eval to refresh.

| Model | Provider | Avg latency | $/request | Pricing model |
|---|---|---|---|---|
| **Qwen2.5-3B-Instruct** | HF ZeroGPU (this Space) | 2.15 s | $0.000* | $9/mo flat (HF Pro) |
| meta-llama/llama-3.2-3b-instruct | OpenRouter (free tier) | 0.89 s | $0.00000 | free up to limit |
| openai/gpt-4o-mini | OpenRouter | ~1.2 s† | $0.00041† | $0.15 / $0.60 per 1M tokens |
| openai/gpt-4.1 | OpenRouter | 2.79 s | $0.00077 | $2.50 / $10 per 1M tokens |

\* Amortized: at the eval volume here (~100 calls/run × a few runs/week) the
flat $9/mo HF Pro fee dominates per-call cost. At sustained production volume
ZeroGPU per-request cost approaches zero; for true scale-out, pay-per-second
GPU on Modal / Replicate becomes cheaper once you exceed ~3M requests/month.

† Estimate at typical eval prompt size (~300 in / 300 out tokens) — not yet in
the captured eval matrix.

### Latency profile

- **Cold start**: 30–60 s the first time after the Space goes idle (HF reclaims
  the GPU slot). Cold-start hit shows up as the first request's `latency_ms` in
  Beacon; subsequent requests within ~5 min reuse the warm worker.
- **Warm requests**: 1.5–3 s for typical eval prompts (100–500 output tokens).
- **TTFT not measurable** in the current `/eval` shape — the endpoint returns
  the complete response (no token streaming). This is acceptable for batch eval
  but means we don't report TTFT for the OSS row in the scorecard.

### Refresh the table from Beacon

The full numbers are in Postgres after any eval run. With the docker-compose
stack up:

```bash
# averaged across the last 24 h
docker exec -it $(docker compose -f deploy/docker-compose.yml ps -q postgres) \
  psql -U beacon -d beacon -c "
  SELECT model,
         count(*) AS requests,
         round(avg(latency_ms)::numeric / 1000, 2) AS avg_latency_s,
         round(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)::numeric / 1000, 2) AS p95_s,
         round(avg(cost_usd)::numeric, 6) AS avg_cost_usd,
         round(sum(cost_usd)::numeric, 4) AS total_cost_usd
  FROM inference_logs
  WHERE ts >= now() - interval '24 hours'
  GROUP BY model
  ORDER BY requests DESC;
  "
```

## Observability + guardrails on the OSS path

Eval traffic routed through the Space is captured by Beacon just like the
frontier traffic — latency, TTFT (where available), tokens, cost, redacted
input/output previews, and PII receipt — visible in the Observability dashboard
at `localhost:5173/observability`.

The same `DefaultGuardrail` from `llmcore.guardrails` runs on the chat path
(input check before the model call) and inside the eval harness (input + output
A/B). The eval's guardrail-on column attributes the risk reduction the safety
layer buys, per model — including the OSS one.

## Operational notes

- **ZeroGPU duration limit**: `@spaces.GPU(duration=120)` caps a single request
  at 120 s. Long-generation tasks (large `max_new_tokens`) can hit this; the
  eval uses `max_new_tokens=512` and stays well within.
- **Concurrency**: ZeroGPU serializes GPU access per Space. The eval harness's
  `concurrency=3` is fine for OpenRouter routes but effectively serializes when
  hitting the OSS Space — expect roughly `n_prompts × avg_latency` wall time
  for the OSS column.
- **Hardware downgrade**: HF occasionally moves Spaces between GPU types
  (A10G ↔ A100). Latency may shift ±20% between eval runs. The published
  scorecard pins the timestamp + git_sha so comparisons stay honest.

## What I'd improve with more time

- **Streaming `/eval`** — switch to `gr.Interface` with `stream=True` so TTFT
  shows up alongside total latency in Beacon.
- **Quantized model** — `Qwen/Qwen2.5-3B-Instruct-GPTQ-Int4` cuts cold-start
  and memory, would let me move to a cheaper hardware class.
- **Dedicated endpoint** — for production, move off ZeroGPU to a dedicated
  inference endpoint with autoscale-to-zero (Modal) for a predictable SLA.
