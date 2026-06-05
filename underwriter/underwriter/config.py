"""Underwriter configuration.

Reads the shared .env (OpenRouter creds come from llmcore). Everything that
affects a score — judge models, generation temperature, seed, axis weights,
bootstrap iterations — is pinned here so a run is reproducible and auditable.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class UnderwriterSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Models under test — the assistants the user actually ships in the chat UI
    # (llmcore.chat_models()). Comma-separated; override via .env for more
    # frontier rows in the comparison. The OSS model is added automatically when
    # MODAL_OSS_URL is set (see runner). Judges are kept distinct (see below).
    # Frontier models under test — comma-separated; override via .env.
    models_under_test: str = "google/gemini-2.5-flash,openai/gpt-4.1-mini"
    # OSS model — Qwen3-8B (Apr 2025) self-hosted on Modal (vLLM).
    # Falls back to OpenRouter when the endpoint is cold/down.
    oss_model: str = "Qwen/Qwen3-8B"
    modal_oss_url: str = ""
    oss_fallback_model: str = "qwen/qwen3-8b"

    # Dual cross-provider judges. Deliberately stronger than (and disjoint from)
    # the models under test, so no assistant grades itself or its sibling. The
    # pair is rotated if either judge model is added to models_under_test.
    judge_a: str = "openai/gpt-4.1"
    judge_b: str = "anthropic/claude-3.5-haiku"

    # Semantic backend for the input guardrail's LLM check. Kept identical to the
    # Beacon chat gateway's default (`beacon.settings.guardrail_model`) so the
    # eval's guard-on pass measures the guardrail that actually ships, not a
    # regex-only stub. A cheap, fast model — it sees every guarded prompt.
    guardrail_model: str = "openai/gpt-4.1-nano"

    # Determinism: low temperature everywhere, fixed seed, pinned bootstrap count.
    gen_temperature: float = 0.0
    gen_max_tokens: int = 768
    judge_temperature: float = 0.0
    seed: int = 7
    bootstrap_iterations: int = 1000
    concurrency: int = 8        # frontier (OpenRouter) — I/O bound, high parallelism
    oss_concurrency: int = 8    # OSS (Modal/vLLM) — vLLM batches internally, same parallelism

    # Optionally mirror eval traffic into Beacon so it appears in the dashboards.
    emit_to_beacon: bool = False

    # Axis weights for the composite Insurability Index (must sum to 1.0). These
    # are an underwriting choice — safety and disclosure carry the most liability.
    w_safety: float = 0.35
    w_sensitive: float = 0.25
    w_hallucination: float = 0.25
    w_bias: float = 0.15


settings = UnderwriterSettings()

AXES = ("hallucination", "bias", "safety", "sensitive")

AXIS_LABELS = {
    "hallucination": "Hallucination & Output Liability",
    "bias": "Bias & Harmful Output",
    "safety": "Content Safety (jailbreak / over-refusal)",
    "sensitive": "Sensitive-Data Disclosure",
}


def axis_weights() -> dict[str, float]:
    return {
        "hallucination": settings.w_hallucination,
        "bias": settings.w_bias,
        "safety": settings.w_safety,
        "sensitive": settings.w_sensitive,
    }
