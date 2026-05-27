"""The SDK's defining promise: capturing telemetry never blocks or breaks the
caller, and delivery degrades gracefully (retry → circuit breaker → bounded
drop-with-counter) when ingestion is unhealthy. All exercised with a fake
transport — no network."""

from __future__ import annotations

import threading
import time
import uuid

from llmobs import InferenceEvent, ObsClient, SDKSettings


def _event() -> InferenceEvent:
    return InferenceEvent(request_id=str(uuid.uuid4()), conversation_id="c", provider="p", model="m")


class CollectingTransport:
    def __init__(self) -> None:
        self.events: list[InferenceEvent] = []

    def send(self, events):
        self.events.extend(events)


class AlwaysFailTransport:
    def send(self, events):
        raise RuntimeError("ingestion down")


class GatedTransport:
    """Blocks inside send() until released, so we can fill the queue."""

    def __init__(self) -> None:
        self.gate = threading.Event()

    def send(self, events):
        self.gate.wait(timeout=5.0)


def test_delivers_all_on_healthy_transport():
    t = CollectingTransport()
    client = ObsClient(SDKSettings(flush_interval_s=0.05, batch_size=10), transport=t)
    for _ in range(25):
        client.emit(_event())
    assert client.flush(timeout=3.0)
    client.close()
    assert len(t.events) == 25
    assert client.stats["sent"] == 25
    assert client.stats["dropped_overflow"] == 0


def test_drops_and_opens_breaker_when_ingestion_down():
    client = ObsClient(
        SDKSettings(
            flush_interval_s=0.05, batch_size=1, max_retries=0,
            breaker_threshold=2, breaker_cooldown_s=30,
        ),
        transport=AlwaysFailTransport(),
    )
    for _ in range(6):
        client.emit(_event())
    client.flush(timeout=3.0)
    client.close()
    # nothing delivered, everything accounted for as a drop, breaker tripped
    assert client.stats["sent"] == 0
    assert client.stats["dropped_failed"] >= 2  # failures up to the threshold
    assert client.stats["dropped_breaker"] >= 1  # shed once the circuit opened
    total_dropped = client.stats["dropped_failed"] + client.stats["dropped_breaker"]
    assert total_dropped == client.stats["emitted"]


def test_emit_is_nonblocking_and_overflow_is_bounded():
    gated = GatedTransport()
    client = ObsClient(SDKSettings(flush_interval_s=0.01, batch_size=1, max_queue=3), transport=gated)
    time.sleep(0.1)  # let the flusher grab the first event and block in send()

    start = time.perf_counter()
    for _ in range(50):
        client.emit(_event())  # must not block even though the transport is stuck
    elapsed = time.perf_counter() - start

    assert elapsed < 0.5, "emit() blocked — telemetry must never stall the caller"
    assert client.stats["dropped_overflow"] >= 1, "bounded queue should shed overflow"
    gated.gate.set()
    client.close()
