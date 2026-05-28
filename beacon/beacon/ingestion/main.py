"""Beacon ingestion API — FastAPI.

Contract: validate fast, hand off to the bus, return 202. The API never writes
to the database on the request path — that's the worker's job — so it stays
cheap and absorbs bursts. Malformed events are routed to a DLQ, not rejected
wholesale, so one bad event can't poison a batch.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from llmobs.schema import InferenceEvent
from prometheus_client import Counter, make_asgi_app

from ..bus import Producer
from ..logging_config import configure_logging
from ..settings import settings

configure_logging()

ACCEPTED = Counter("beacon_ingest_accepted_total", "Valid events produced to the bus")
REJECTED = Counter("beacon_ingest_rejected_total", "Invalid events routed to DLQ")

_producer: Producer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _producer
    _producer = Producer(settings.redpanda_brokers)
    await _producer.start()
    try:
        yield
    finally:
        await _producer.stop()


app = FastAPI(title="Beacon Ingestion", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


def _check_auth(api_key: str | None) -> None:
    if api_key != settings.ingest_api_key:
        raise HTTPException(401, "invalid or missing x-api-key")


@app.post("/v1/ingest", status_code=202)
async def ingest(request: Request, x_api_key: str | None = Header(default=None)) -> dict:
    _check_auth(x_api_key)
    body: Any = await request.json()
    raw_events = body.get("events", body) if isinstance(body, dict) else body
    if not isinstance(raw_events, list):
        raise HTTPException(400, "expected a list of events or {\"events\": [...]}")

    accepted = rejected = 0
    for raw in raw_events:
        try:
            event = InferenceEvent.model_validate(raw)
        except Exception:  # malformed → DLQ, keep going
            await _producer.send(
                settings.topic_dlq, key="malformed", value=json.dumps(raw, default=str).encode()
            )
            rejected += 1
            continue
        await _producer.send(
            settings.topic_events, key=event.request_id, value=event.model_dump_json().encode()
        )
        accepted += 1

    ACCEPTED.inc(accepted)
    REJECTED.inc(rejected)
    return {"accepted": accepted, "rejected": rejected}


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}
