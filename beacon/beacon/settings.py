"""Beacon service settings (gateway, ingestion, worker). Reads the shared .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BeaconSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Storage
    database_url: str = "postgresql+psycopg://beacon:beacon@localhost:5432/beacon"

    # Event bus
    redpanda_brokers: str = "localhost:9092"
    topic_events: str = "inference-events"
    topic_dlq: str = "inference-events-dlq"
    consumer_group: str = "beacon-worker"

    # Ingestion auth
    ingest_api_key: str = "dev-ingest-key"

    # Gateway
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    gateway_port: int = 8000
    ingestion_port: int = 8088

    # Semantic guardrail judge — must not be in the chat model list
    guardrail_model: str = "openai/gpt-4.1-nano"


settings = BeaconSettings()
