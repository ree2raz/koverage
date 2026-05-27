"""The inference-event contract.

This is the single shape that flows SDK → ingestion → bus → worker → store. The
SDK *owns* it (services depend on the SDK's contract, not the other way round),
so emitter and consumer can never drift. `request_id` is the idempotency key.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal["ok", "error", "cancelled"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InferenceEvent(BaseModel):
    # identity / correlation
    request_id: str  # idempotency key (uuid4)
    conversation_id: str
    message_id: str = ""
    session_id: str = ""

    # what ran
    provider: str
    model: str
    status: Status = "ok"
    error_type: str = ""

    # performance
    latency_ms: int = 0
    ttft_ms: int = 0  # time-to-first-token (streaming)

    # usage / cost
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

    # content (already redacted + truncated by the SDK before it ever leaves)
    input_preview: str = ""
    output_preview: str = ""
    redaction_counts: dict[str, int] = Field(default_factory=dict)  # privacy receipt

    # escape hatch + timing
    meta: dict[str, Any] = Field(default_factory=dict)
    ts: datetime = Field(default_factory=_utcnow)  # request start (event time)
    ingested_at: datetime | None = None  # set by the pipeline on arrival


class IngestBatch(BaseModel):
    """Envelope the SDK POSTs to the ingestion API."""

    events: list[InferenceEvent]
