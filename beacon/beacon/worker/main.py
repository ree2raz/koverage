"""Beacon worker — consumes inference events and persists them idempotently.

At-least-once: we commit the offset only after a successful DB write, so a crash
re-delivers rather than loses. Idempotent: `INSERT ... ON CONFLICT (request_id)
DO NOTHING` makes re-delivery a no-op. Poison messages (unparseable / invalid)
go to the DLQ so one bad record can't wedge the consumer group.

Run:  python -m beacon.worker.main
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from llmobs.schema import InferenceEvent
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..bus import Producer, make_consumer
from ..db.base import SessionLocal
from ..db.models import InferenceLog
from ..settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s worker: %(message)s")
log = logging.getLogger("beacon.worker")


def _to_row(event: InferenceEvent) -> dict:
    return {
        "request_id": event.request_id,
        "conversation_id": event.conversation_id,
        "message_id": event.message_id,
        "session_id": event.session_id,
        "provider": event.provider,
        "model": event.model,
        "status": event.status,
        "error_type": event.error_type,
        "latency_ms": event.latency_ms,
        "ttft_ms": event.ttft_ms,
        "prompt_tokens": event.prompt_tokens,
        "completion_tokens": event.completion_tokens,
        "total_tokens": event.total_tokens or (event.prompt_tokens + event.completion_tokens),
        "cost_usd": event.cost_usd,
        "input_preview": event.input_preview,
        "output_preview": event.output_preview,
        "redaction_counts": event.redaction_counts,
        "meta": event.meta,
        "ts": event.ts,
    }


async def _persist(event: InferenceEvent) -> None:
    stmt = (
        pg_insert(InferenceLog)
        .values(**_to_row(event))
        .on_conflict_do_nothing(index_elements=["request_id"])
    )
    async with SessionLocal() as session:
        await session.execute(stmt)
        await session.commit()


async def run() -> None:
    consumer = make_consumer(
        topic=settings.topic_events,
        brokers=settings.redpanda_brokers,
        group=settings.consumer_group,
    )
    dlq = Producer(settings.redpanda_brokers)
    await consumer.start()
    await dlq.start()
    log.info("consuming %s (group=%s)", settings.topic_events, settings.consumer_group)
    try:
        async for msg in consumer:
            try:
                event = InferenceEvent.model_validate_json(msg.value)
                event.ingested_at = datetime.now(timezone.utc)
                await _persist(event)
            except Exception as exc:  # poison message → DLQ, don't block the group
                log.warning("routing bad message to DLQ: %s", exc)
                await dlq.send(settings.topic_dlq, key="poison", value=msg.value)
            await consumer.commit()  # at-least-once: commit only after handling
    finally:
        await consumer.stop()
        await dlq.stop()


if __name__ == "__main__":
    asyncio.run(run())
