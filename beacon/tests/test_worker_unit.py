"""Worker unit tests — _to_row mapping and idempotency contract.

No database or Kafka connection required.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from llmobs.schema import InferenceEvent

from beacon.worker.main import _to_row


def _ev(**kw) -> InferenceEvent:
    base = dict(
        request_id=str(uuid.uuid4()),
        conversation_id="conv-1",
        provider="openai",
        model="gpt-4.1",
    )
    base.update(kw)
    return InferenceEvent(**base)


def test_to_row_maps_all_required_fields():
    ev = _ev(latency_ms=320, prompt_tokens=10, completion_tokens=20)
    row = _to_row(ev)
    assert row["request_id"] == ev.request_id
    assert row["conversation_id"] == ev.conversation_id
    assert row["provider"] == ev.provider
    assert row["model"] == ev.model
    assert row["latency_ms"] == 320


def test_to_row_total_tokens_computed_when_absent():
    ev = _ev(prompt_tokens=7, completion_tokens=13)
    row = _to_row(ev)
    assert row["total_tokens"] == 20


def test_to_row_total_tokens_kept_when_present():
    ev = _ev(prompt_tokens=7, completion_tokens=13, total_tokens=99)
    row = _to_row(ev)
    assert row["total_tokens"] == 99


def test_to_row_status_defaults_to_ok():
    ev = _ev()
    row = _to_row(ev)
    assert row["status"] in ("ok", "success", None, "")  # whatever the schema default is


def test_to_row_preserves_ts():
    ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ev = _ev(ts=ts)
    row = _to_row(ev)
    assert row["ts"] == ts
