"""Ollive OSS Inference — Modal + vLLM.

Serves Qwen3-8B on an A10G via vLLM, exposing an OpenAI-compatible API at
/v1/chat/completions. vLLM's continuous batching handles concurrent requests.

Deploy:
    modal deploy modal-app/qwen_app.py

Modal prints the endpoint URL. Set it as MODAL_OSS_URL in platform/.env and
restart the gateway. The served model name is 'Qwen/Qwen3-8B'.

Cost: A10G at ~$1.10/hr, charged per-second. Scales to zero after
scaledown_window of idle.

Thinking mode: Qwen3 supports extended chain-of-thought. This endpoint runs
in standard (non-thinking) mode by default. To enable thinking for a request:
    extra_body={"chat_template_kwargs": {"enable_thinking": True}}
"""

from __future__ import annotations

import subprocess

import modal

MINUTES = 60

MODEL_ID = "Qwen/Qwen3-8B"
MAX_MODEL_LEN = 16_384   # 16 k context fits on A10G with ~1.75 GiB KV cache

app = modal.App("ollive-oss-inference")

# Persistent volume — model downloads once on first deploy, reused after.
hf_cache = modal.Volume.from_name("ollive-hf-cache", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm>=0.8",
        "huggingface_hub[hf_transfer]>=0.26",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

_VLLM_CMD = " ".join([
    "vllm", "serve", MODEL_ID,
    "--host", "0.0.0.0",
    "--port", "8000",
    "--dtype", "auto",
    "--max-model-len", str(MAX_MODEL_LEN),
    "--served-model-name", MODEL_ID,
    "--trust-remote-code",
    "--async-scheduling",
    "--uvicorn-log-level", "warning",
])


@app.function(
    image=image,
    gpu="A10G",
    scaledown_window=5 * MINUTES,
    timeout=10 * MINUTES,
    max_containers=1,
    volumes={"/root/.cache/huggingface": hf_cache},
)
@modal.concurrent(max_inputs=50)
@modal.web_server(port=8000, startup_timeout=10 * MINUTES)
def serve():
    """Start vLLM; @modal.web_server proxies port 8000 once it's healthy."""
    subprocess.Popen(_VLLM_CMD, shell=True)


@app.local_entrypoint()
def smoke_test():
    """Quick sanity check: modal run modal-app/qwen_app.py"""
    import urllib.request, json  # noqa: E401

    url = serve.get_web_url()
    req = urllib.request.Request(
        f"{url}/v1/chat/completions",
        data=json.dumps({
            "model": MODEL_ID,
            "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
            "max_tokens": 8,
            "temperature": 0,
        }).encode(),
        headers={"Content-Type": "application/json"},
    )
    resp = json.loads(urllib.request.urlopen(req).read())
    print(resp["choices"][0]["message"]["content"])
