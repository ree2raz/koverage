"""Ingestion API hardening tests — auth, validation, DLQ routing.

All tests run offline: Kafka/Redpanda is replaced with an AsyncMock so
the FastAPI lifespan completes without a real broker.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from beacon.ingestion.main import app

VALID_KEY = "dev-ingest-key"


def _event(**overrides) -> dict:
    base = {
        "request_id": str(uuid.uuid4()),
        "conversation_id": "conv-1",
        "provider": "openai",
        "model": "gpt-4.1",
    }
    base.update(overrides)
    return base


@pytest.fixture
def ingestion_client():
    """TestClient with Kafka Producer replaced by an AsyncMock."""
    with patch("beacon.ingestion.main.Producer") as MockProducer:
        mock_prod = AsyncMock()
        MockProducer.return_value = mock_prod
        with TestClient(app) as c:
            yield c, mock_prod


# ── auth ────────────────────────────────────────────────────────────────────

def test_missing_api_key_rejected(ingestion_client):
    c, _ = ingestion_client
    r = c.post("/v1/ingest", json={"events": [_event()]})
    assert r.status_code == 401


def test_wrong_api_key_rejected(ingestion_client):
    c, _ = ingestion_client
    r = c.post("/v1/ingest", json={"events": [_event()]}, headers={"x-api-key": "bad-key"})
    assert r.status_code == 401


# ── validation ───────────────────────────────────────────────────────────────

def test_valid_event_accepted(ingestion_client):
    c, mock_prod = ingestion_client
    r = c.post("/v1/ingest", json={"events": [_event()]}, headers={"x-api-key": VALID_KEY})
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 1
    assert body["rejected"] == 0


def test_malformed_event_routed_to_dlq(ingestion_client):
    c, mock_prod = ingestion_client
    bad = {"not_a_valid_field": "garbage"}
    r = c.post("/v1/ingest", json={"events": [bad]}, headers={"x-api-key": VALID_KEY})
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 0
    assert body["rejected"] == 1
    # DLQ send must have been called with the DLQ topic
    assert mock_prod.send.called
    dlq_call = mock_prod.send.call_args_list[0]
    assert "dlq" in dlq_call.args[0]


def test_mixed_batch_counts_correctly(ingestion_client):
    c, mock_prod = ingestion_client
    events = [_event(), {"garbage": True}, _event()]
    r = c.post("/v1/ingest", json={"events": events}, headers={"x-api-key": VALID_KEY})
    assert r.status_code == 202
    body = r.json()
    assert body["accepted"] == 2
    assert body["rejected"] == 1


def test_body_without_events_key_rejected(ingestion_client):
    c, _ = ingestion_client
    r = c.post("/v1/ingest", json="not-a-list", headers={"x-api-key": VALID_KEY})
    assert r.status_code == 400


def test_request_id_used_as_kafka_key(ingestion_client):
    c, mock_prod = ingestion_client
    ev = _event()
    r = c.post("/v1/ingest", json={"events": [ev]}, headers={"x-api-key": VALID_KEY})
    assert r.status_code == 202
    # The producer.send call uses request_id as the Kafka message key
    call_args = mock_prod.send.call_args_list[0]
    assert call_args.kwargs.get("key") == ev["request_id"]
