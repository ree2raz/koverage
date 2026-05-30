"""SDK configuration. Reads env (BEACON_*) but every value is overridable in code."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SDKSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ingest_url: str = "http://localhost:8088/v1/ingest"
    ingest_api_key: str = "dev-ingest-key"

    # Non-blocking buffer behaviour
    batch_size: int = 20  # flush when this many events are queued
    flush_interval_s: float = 1.0  # ...or at least this often
    max_queue: int = 10_000  # bounded; overflow is dropped (and counted)
    preview_chars: int = 4000  # truncate previews after redaction (kept generous so
    #                            the dashboard shows full payloads in a scroll box)

    # Delivery resilience
    max_retries: int = 4
    backoff_base_s: float = 0.2
    backoff_max_s: float = 5.0
    breaker_threshold: int = 5  # consecutive failures before the circuit opens
    breaker_cooldown_s: float = 10.0

    # Head-based sampling (1.0 = log everything)
    sample_rate: float = 1.0
