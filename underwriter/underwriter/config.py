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
    models_under_test: str = "openai/gpt-4o-mini"
    oss_model: str = "Qwen/Qwen2.5-3B-Instruct"
    # Self-hosted OSS model, served on Modal (vLLM behind a Modal endpoint).
    modal_oss_url: str = ""    # Modal @fastapi_endpoint
    # OpenRouter fallback when the Modal endpoint is unresponsive — keeps a full
    # eval run from collapsing on a single outage. Same Qwen family.
    oss_fallback_model: str = "qwen/qwen-2.5-7b-instruct"

    # Dual cross-provider judges. Deliberately stronger than (and disjoint from)
    # the models under test, so no assistant grades itself or its sibling.
    judge_a: str = "openai/gpt-4.1"
    judge_b: str = "google/gemini-2.5-flash"

    # Determinism: low temperature everywhere, fixed seed, pinned bootstrap count.
    gen_temperature: float = 0.0
    gen_max_tokens: int = 768
    judge_temperature: float = 0.0
    seed: int = 7
    bootstrap_iterations: int = 1000
    concurrency: int = 3

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
