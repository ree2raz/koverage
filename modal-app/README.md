# Modal OSS Inference: Qwen3-8B on vLLM

Self-hosted open-source model serving for the Underwriter eval and the chat UI's
OSS path. Runs **Qwen3-8B** on an A10G GPU via [Modal](https://modal.com), behind
vLLM's **OpenAI-compatible API** (`/v1/chat/completions`): the same wire protocol
every other provider in the platform speaks, so no custom client is needed.

## What this is

A Modal app (`qwen_app.py`) that serves an OSS model for both the Underwriter
evaluation harness and the chat UI's OSS path.

**Model:** `Qwen/Qwen3-8B` · **GPU:** A10G (24 GB) · **Server:** vLLM (OpenAI-compatible)
· **Context:** 16k tokens (`MAX_MODEL_LEN=16384`)

## Why Modal

- **Scale-to-zero** - pay only for GPU-seconds during eval runs and chat, not idle
  time (`scaledown_window=5min`).
- **One-command deploy** - `modal deploy modal-app/qwen_app.py`.
- **OpenAI-compatible** - vLLM serves `/v1/chat/completions`, so the platform's
  `OpenAICompatibleBackend` just works; the OSS path is a base-URL swap, not new code.
- **Weights cached on a Volume** - the 8B weights download once to a persistent
  `modal.Volume` (`koverage-hf-cache`) and are reused across deploys, instead of being
  baked into a multi-GB image.

## Design notes

- **Why 16k context, not 32k?** On an A10G the KV cache budget is tight: 32k needed
  ~4.5 GiB of KV cache but only ~3.76 GiB was free, causing an OOM at startup. 16k
  needs ~1.75 GiB: comfortable headroom, and more than enough for the eval prompts
  and chat turns.
- **Concurrency** - `@modal.concurrent(max_inputs=50)`; vLLM's continuous batching
  handles concurrent requests inside a single container (`max_containers=1`).
- **Web server pattern** - `@modal.web_server(port=8000, startup_timeout=10min)`
  proxies vLLM's port once it's healthy; no manual health-check polling.
- **Thinking mode** - Qwen3 supports extended chain-of-thought. This endpoint runs
  in standard (non-thinking) mode by default; pass
  `extra_body={"chat_template_kwargs": {"enable_thinking": True}}` to enable it.

## Cost & latency (A10G)

| Metric                          | Value                                                            |
| ------------------------------- | ---------------------------------------------------------------- |
| GPU                             | A10G (24 GB)                                                     |
| Price                           | ~$1.10/hr (Modal, per-second billing)                            |
| Cold start                      | ~1–3 min first call (weights from Volume + vLLM warmup)          |
| Warm latency (single-turn chat) | ~0.8–2 s per request                                             |
| Per-item eval latency           | ~27 s (full multi-turn prompt on one A10G, cold-start amortised) |
| Throughput                      | vLLM continuous batching; up to ~50 concurrent inputs            |
| Idle cost                       | $0 (scales to zero after 5 min idle)                             |

## Deploy

```bash
modal deploy modal-app/qwen_app.py
```

Modal prints the endpoint URL. Put it in `platform/.env`:

```
MODAL_OSS_URL=https://<your-endpoint>.modal.run
OSS_MODEL=Qwen/Qwen3-8B      # exact case: lowercase routes to OpenRouter, not Modal
```

The platform appends `/v1` automatically (see `core/llmcore/config.py`). The served
model name is `Qwen/Qwen3-8B`.

### Smoke test

```bash
modal run modal-app/qwen_app.py      # prints the model's reply to a tiny prompt
```

## Routing & fallback

`core/llmcore/providers/router.py` maps the `Qwen/Qwen3-8B` catalog entry
(`gateway="oss"`) to this endpoint via `MODAL_OSS_URL`, wrapping it in the standard
`OpenAICompatibleBackend`. When `MODAL_OSS_URL` is unset or the endpoint is
unreachable, the Underwriter runner and chat path fall back to `qwen/qwen3-8b` on
OpenRouter so a run still completes. See
`underwriter/underwriter/runner.py::_resolve_oss_backend`.

## Files

- `qwen_app.py`: the Modal app: image, Volume, vLLM serve command, web server, smoke test.
