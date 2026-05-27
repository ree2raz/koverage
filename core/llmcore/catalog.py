"""Model catalog: the single source of truth for which models we expose, who
provides them, and what they cost.

One catalog powers three things:
  - the model selector in the chat UI,
  - cost attribution in Beacon's observability (USD per request/conversation),
  - the model set Underwriter compares.

Prices are USD per 1,000,000 tokens and are *indicative* — they drift, so they
live in exactly one place. All hosted models are reached through OpenRouter
(one key, many providers), which is how we satisfy "multi-provider support"
without N separate integrations. The OSS model is self-hosted (HF Space), so it
has no per-token price; its cost is GPU-time, handled separately.
"""

from __future__ import annotations

from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str  # id used on the wire (OpenRouter slug, or OSS model id)
    label: str  # human-friendly name for the UI
    provider: str  # upstream vendor: openai | anthropic | google | deepseek | xai | oss
    gateway: str = "openrouter"  # which endpoint serves it: openrouter | oss
    prompt_usd_per_1m: float = 0.0
    completion_usd_per_1m: float = 0.0
    context_tokens: int = 0
    notes: str = ""


# Indicative pricing (USD / 1M tokens). Update here when vendors change rates.
CATALOG: dict[str, ModelInfo] = {
    m.id: m
    for m in [
        ModelInfo(
            id="openai/gpt-4.1",
            label="GPT-4.1",
            provider="openai",
            prompt_usd_per_1m=2.00,
            completion_usd_per_1m=8.00,
            context_tokens=1_047_576,
        ),
        ModelInfo(
            id="openai/gpt-4.1-mini",
            label="GPT-4.1 mini",
            provider="openai",
            prompt_usd_per_1m=0.40,
            completion_usd_per_1m=1.60,
            context_tokens=1_047_576,
        ),
        ModelInfo(
            id="anthropic/claude-3.7-sonnet",
            label="Claude 3.7 Sonnet",
            provider="anthropic",
            prompt_usd_per_1m=3.00,
            completion_usd_per_1m=15.00,
            context_tokens=200_000,
        ),
        ModelInfo(
            id="google/gemini-2.5-pro",
            label="Gemini 2.5 Pro",
            provider="google",
            prompt_usd_per_1m=1.25,
            completion_usd_per_1m=10.00,
            context_tokens=1_048_576,
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
            prompt_usd_per_1m=0.27,
            completion_usd_per_1m=1.10,
            context_tokens=64_000,
        ),
        ModelInfo(
            id="x-ai/grok-2",
            label="Grok 2",
            provider="xai",
            prompt_usd_per_1m=2.00,
            completion_usd_per_1m=10.00,
            context_tokens=131_072,
        ),
        # Self-hosted open-source model (HF Space, ZeroGPU). Cost is GPU-time,
        # not per-token; see Beacon cost notes. Reached via the "oss" gateway.
        ModelInfo(
            id="google/gemma-3n-e4b-it",
            label="Gemma 3n E4B (self-hosted)",
            provider="oss",
            gateway="oss",
            context_tokens=32_000,
            notes="Self-hosted on Hugging Face ZeroGPU; cost measured as GPU-seconds.",
        ),
    ]
}


def get_model(model_id: str) -> ModelInfo | None:
    return CATALOG.get(model_id)


def models_for_gateway(gateway: str) -> list[ModelInfo]:
    return [m for m in CATALOG.values() if m.gateway == gateway]
