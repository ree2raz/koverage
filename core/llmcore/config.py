"""Shared LLM configuration. Loads from environment / .env (see .env.example).

Only the model-provider knobs live here — the bits both modules need. Beacon's
ingestion/datastore settings and Underwriter's judge settings live in their own
config modules so the modules stay decoupled. `extra="ignore"` lets all three
read the same .env without clashing.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenRouter is the primary gateway: one key, many providers/models.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "openai/gpt-4.1"

    # Self-hosted OSS model, served on Modal (vLLM OpenAI-compatible endpoint).
    # MODAL_OSS_URL should be the root URL printed by `modal deploy` — the
    # platform appends /v1 automatically when building the backend.
    oss_model: str = "Qwen/Qwen3-8B"
    modal_oss_url: str = ""
    modal_oss_api_key: str = "modal"  # Modal public endpoints accept any non-empty string

    # Generation defaults.
    temperature: float = 0.7
    max_tokens: int = 1024
    seed: int = 7

    # Attribution headers OpenRouter shows on its dashboard (optional, harmless).
    app_referer: str = "https://github.com/ollive/platform"
    app_title: str = "Ollive Platform"


settings = CoreSettings()
