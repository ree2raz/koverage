"""Ollive OSS Inference Backend on Modal.

Serves Qwen2.5-3B-Instruct on an A10G with a single FastAPI endpoint. Used as
the OSS path for the chat + Underwriter eval when the HF Space is too flaky
to depend on for live demos.

Deploy:
    modal deploy modal-app/qwen_app.py

Modal will print a URL like:
    https://<user>--ollive-qwen-qwenserver-generate.modal.run

Set that as MODAL_OSS_URL in platform/.env, restart the gateway, and the chat's
"Qwen 2.5 3B" entry now routes to Modal instead of HF Spaces.

Cost: A10G at ~$1.10/hr, charged per-second of active runtime. The container
scales to zero after `scaledown_window` seconds of idle (default 5 min here),
so a full Loom demo session typically costs < $0.30. Stop the app entirely
when done:
    modal app stop ollive-qwen
"""

from __future__ import annotations

import modal

MODEL_ID = "Qwen/Qwen2.5-3B-Instruct"
MAX_NEW_TOKENS = 512
TEMPERATURE = 0.7

SYSTEM_PROMPT = (
    "You are a helpful, honest, and careful assistant. Hold a natural multi-turn "
    "conversation and remember what the user told you earlier. If unsure of a fact, "
    "say so rather than guessing."
)

app = modal.App("ollive-qwen")


def _download_weights() -> None:
    """Bake Qwen weights into the image so containers cold-start from disk,
    not from a 6 GB HF download (~30 s → ~10 s)."""
    from huggingface_hub import snapshot_download

    snapshot_download(MODEL_ID, ignore_patterns=["*.pt", "*.bin"])  # safetensors only


image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "transformers>=4.45",
        "torch>=2.4",
        "accelerate>=0.34",
        "huggingface_hub[hf_transfer]>=0.26",
        "fastapi[standard]>=0.115",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})  # faster snapshot download at build
    .run_function(_download_weights)
)


@app.cls(
    image=image,
    gpu="A10G",
    scaledown_window=300,  # keep warm 5 min after last request
    timeout=120,            # per-request cap
)
class QwenServer:
    @modal.enter()
    def load(self) -> None:
        """Loads Qwen onto the GPU exactly once per container lifetime."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16,
            device_map="cuda",
        )

    @modal.fastapi_endpoint(method="POST")
    def generate(self, body: dict) -> dict:
        """POST {prompt, system} → {text, latency_s, completion_tokens}.

        Same response shape the HF Space exposes, so the platform's OSS backend
        is interchangeable between the two without changing the contract.
        """
        import time

        import torch

        prompt = body.get("prompt", "") or ""
        system = body.get("system", "") or SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        t0 = time.perf_counter()
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                temperature=TEMPERATURE,
                do_sample=TEMPERATURE > 0,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        new_tokens = out[0][inputs["input_ids"].shape[1]:]
        reply = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        latency = time.perf_counter() - t0

        return {
            "text": reply,
            "latency_s": round(latency, 3),
            "completion_tokens": int(len(new_tokens)),
        }
