# Modal OSS Backend (Qwen2.5-3B)

The self-hosted OSS path for the chat + Underwriter eval: Qwen2.5-3B served on a
Modal GPU endpoint with a `{prompt, system} → {text, latency_s, completion_tokens}`
contract. The chat router and the eval harness both reach the OSS model here.

## One-time setup

```bash
pip install modal
modal token new      # opens browser, authenticates
```

## Deploy

```bash
modal deploy modal-app/qwen_app.py
```

Modal prints a URL like:

```
https://<user>--ollive-qwen-qwenserver-generate.modal.run
```

Copy that into `platform/.env`:

```
MODAL_OSS_URL=https://<user>--ollive-qwen-qwenserver-generate.modal.run
```

Restart the gateway so it re-reads `.env`:

```bash
docker compose -f deploy/docker-compose.yml restart gateway
```

The chat's "Qwen 2.5 3B" entry and the Underwriter OSS row both route through
this Modal endpoint. Without `MODAL_OSS_URL` set, the OSS model is simply absent
from the chat selector and the eval matrix.

## Cost

A10G is **$1.10/hr**, billed per-second of active runtime. The container
auto-scales to zero after 5 minutes idle (`scaledown_window=300`). A typical
Loom recording session costs **well under $0.30**.

## Stop when done

```bash
modal app stop ollive-qwen
```

Or leave it deployed — it costs nothing when idle, only spins up on requests.

## Latency profile vs HF Spaces

| | HF Spaces ZeroGPU | Modal A10G |
|---|---|---|
| Cold start | 30–60 s | 8–15 s |
| Warm request | 1.5–3 s | 0.8–2 s |
| Concurrent shedding | yes (CancelledError) | no |
| Pricing | $9/mo flat (HF Pro) | $1.10/hr active |
| Best for | submission artifact | live demos |
