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

    # Optional direct provider keys (Underwriter judges / direct routing).
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # Self-hosted OSS model, served on Modal (vLLM behind a Modal endpoint).
    oss_model: str = "Qwen/Qwen2.5-3B-Instruct"
    modal_oss_url: str = ""    # Modal @fastapi_endpoint POST URL

    # Generation defaults.
    temperature: float = 0.7
    max_tokens: int = 1024
    seed: int = 7

    # Attribution headers OpenRouter shows on its dashboard (optional, harmless).
    app_referer: str = "https://github.com/ollive/platform"
    app_title: str = "Ollive Platform"


settings = CoreSettings()
