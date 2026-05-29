"""Model catalog: the single source of truth for which models we expose, who
provides them, and what they cost.

One catalog powers three things:
  - the model selector in the chat UI (chat=True models only),
  - cost attribution in Beacon's observability (USD per request/conversation),
  - the model set Underwriter compares.

Prices are USD per 1,000,000 tokens and are *indicative* — they drift, so they
live in exactly one place. All hosted models are reached through OpenRouter
(one key, many providers), which is how we satisfy "multi-provider support"
without N separate integrations.

Chat UI exposes 4 closed-source families, cheapest model per family:
  openai/gpt-4o-mini · anthropic/claude-3.5-haiku
  google/gemini-2.5-flash · deepseek/deepseek-chat
"""

from __future__ import annotations

from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str               # wire id: OpenRouter slug or OSS model id
    label: str            # human-friendly name shown in the UI
    provider: str         # upstream vendor: openai | anthropic | google | deepseek | oss
    gateway: str = "openrouter"   # openrouter | oss
    chat: bool = True     # True → shown in chat model selector
    prompt_usd_per_1m: float = 0.0
    completion_usd_per_1m: float = 0.0
    context_tokens: int = 0
    notes: str = ""


# Indicative pricing (USD / 1M tokens). Update here when vendors change rates.
CATALOG: dict[str, ModelInfo] = {
    m.id: m
    for m in [
        # ── 4 closed-source families, cheapest model each ─────────────────────
        ModelInfo(
            id="openai/gpt-4o-mini",
            label="GPT-4o mini",
            provider="openai",
            prompt_usd_per_1m=0.15,
            completion_usd_per_1m=0.60,
            context_tokens=128_000,
        ),
        ModelInfo(
            id="anthropic/claude-3.5-haiku",
            label="Claude 3.5 Haiku",
            provider="anthropic",
            prompt_usd_per_1m=0.80,
            completion_usd_per_1m=4.00,
            context_tokens=200_000,
        ),
        ModelInfo(
            id="google/gemini-2.5-flash",
            label="Gemini 2.5 Flash",
            provider="google",
            prompt_usd_per_1m=0.30,
            completion_usd_per_1m=2.50,
            context_tokens=1_048_576,
        ),
        ModelInfo(
            id="deepseek/deepseek-chat",
            label="DeepSeek V3",
            provider="deepseek",
            prompt_usd_per_1m=0.20,
            completion_usd_per_1m=0.77,
            context_tokens=64_000,
        ),

        # ── Underwriter judges + models under test (not shown in chat UI) ─────
        ModelInfo(
            id="openai/gpt-4.1",
            label="GPT-4.1",
            provider="openai",
            chat=False,
            prompt_usd_per_1m=2.00,
            completion_usd_per_1m=8.00,
            context_tokens=1_047_576,
            notes="Used as Underwriter judge and frontier baseline.",
        ),

        # ── OSS models (Underwriter only, not shown in chat UI) ───────────────
        ModelInfo(
            id="meta-llama/llama-3.2-3b-instruct",
            label="Llama 3.2 3B (OSS)",
            provider="oss",
            gateway="openrouter",
            chat=False,
            prompt_usd_per_1m=0.015,
            completion_usd_per_1m=0.025,
            context_tokens=131_072,
            notes="Meta Llama 3.2 3B via OpenRouter — Underwriter OSS baseline.",
        ),
        ModelInfo(
            id="Qwen/Qwen2.5-3B-Instruct",
            label="Qwen2.5 3B (HF Space)",
            provider="oss",
            gateway="oss",
            chat=True,
            context_tokens=32_768,
            notes="Qwen2.5-3B-Instruct on HF Space ZeroGPU; cost in GPU-seconds.",
        ),
    ]
}


def get_model(model_id: str) -> ModelInfo | None:
    return CATALOG.get(model_id)


def models_for_gateway(gateway: str) -> list[ModelInfo]:
    return [m for m in CATALOG.values() if m.gateway == gateway]


def chat_models() -> list[ModelInfo]:
    """Models shown in the chat UI selector."""
    return [m for m in CATALOG.values() if m.chat]
