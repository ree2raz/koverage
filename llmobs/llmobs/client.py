"""Non-blocking observability client.

The contract: capturing telemetry must NEVER slow or break the chat path.
`emit()` only puts an event on a bounded in-memory queue and returns; a daemon
thread batches and ships them. If ingestion is down we retry with backoff, trip
a circuit breaker, and drop-with-counter once the bound is hit — the product
keeps working, we just lose some telemetry and can prove how much.

Transport is injected, so tests exercise the queue/retry/breaker logic with a
fake sink and zero network.
"""

from __future__ import annotations

import atexit
import logging
import queue
import random
import threading
import time
from typing import Protocol

import httpx

from .config import SDKSettings
from .schema import IngestBatch, InferenceEvent

log = logging.getLogger("llmobs")


class Transport(Protocol):
    def send(self, events: list[InferenceEvent]) -> None:
        """Deliver a batch. Raise on failure (the client handles retry/breaker)."""
        ...


class HTTPTransport:
    def __init__(self, url: str, api_key: str, timeout: float = 5.0) -> None:
        self.url = url
        self.api_key = api_key
        self._client = httpx.Client(timeout=timeout)

    def send(self, events: list[InferenceEvent]) -> None:
        body = IngestBatch(events=events).model_dump_json()
        resp = self._client.post(
            self.url,
            content=body,
            headers={"content-type": "application/json", "x-api-key": self.api_key},
        )
        resp.raise_for_status()

    def close(self) -> None:
        self._client.close()


class ObsClient:
    def __init__(self, settings: SDKSettings | None = None, transport: Transport | None = None) -> None:
        self.settings = settings or SDKSettings()
        self.transport = transport or HTTPTransport(
            self.settings.ingest_url, self.settings.ingest_api_key
        )

        self._queue: queue.Queue[InferenceEvent] = queue.Queue(maxsize=self.settings.max_queue)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._pending = 0  # queued-but-not-yet-handled, for flush()

        # circuit breaker
        self._consec_failures = 0
        self._breaker_open_until = 0.0

        self.stats = {"emitted": 0, "sent": 0, "dropped_overflow": 0, "dropped_breaker": 0,
                      "dropped_failed": 0, "sampled_out": 0}

        self._thread = threading.Thread(target=self._loop, name="llmobs-flusher", daemon=True)
        self._thread.start()
        atexit.register(self.close)

    # ── public API ──────────────────────────────────────────────────────────
    def emit(self, event: InferenceEvent) -> None:
        if self.settings.sample_rate < 1.0 and random.random() > self.settings.sample_rate:
            with self._lock:
                self.stats["sampled_out"] += 1
            return
        try:
            self._queue.put_nowait(event)
            with self._lock:
                self._pending += 1
                self.stats["emitted"] += 1
        except queue.Full:
            with self._lock:
                self.stats["dropped_overflow"] += 1

    def flush(self, timeout: float = 5.0) -> bool:
        """Block until the queue has drained (or timeout). Returns True if drained."""
        with self._cond:
            return self._cond.wait_for(lambda: self._pending == 0, timeout=timeout)

    def close(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        self._thread.join(timeout=self.settings.flush_interval_s + 5.0)
        if isinstance(self.transport, HTTPTransport):
            self.transport.close()

    # ── background flusher ────────────────────────────────────────────────────
    def _loop(self) -> None:
        while not self._stop.is_set():
            batch = self._drain()
            if batch:
                self._ship(batch)
        # drain whatever is left on shutdown
        leftover = self._drain(block=False)
        if leftover:
            self._ship(leftover)

    def _drain(self, block: bool = True) -> list[InferenceEvent]:
        batch: list[InferenceEvent] = []
        try:
            first = (
                self._queue.get(timeout=self.settings.flush_interval_s)
                if block
                else self._queue.get_nowait()
            )
            batch.append(first)
        except queue.Empty:
            return batch
        while len(batch) < self.settings.batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _ship(self, batch: list[InferenceEvent]) -> None:
        delivered = self._send_with_retry(batch)
        with self._cond:
            if delivered:
                self.stats["sent"] += len(batch)
            self._pending -= len(batch)
            self._cond.notify_all()

    def _send_with_retry(self, batch: list[InferenceEvent]) -> bool:
        now = time.monotonic()
        if now < self._breaker_open_until:  # circuit open: shed load
            with self._lock:
                self.stats["dropped_breaker"] += len(batch)
            return False

        for attempt in range(self.settings.max_retries + 1):
            try:
                self.transport.send(batch)
                self._consec_failures = 0
                return True
            except Exception as exc:  # noqa: BLE001 — telemetry must never raise upward
                if attempt < self.settings.max_retries:
                    delay = min(
                        self.settings.backoff_base_s * (2**attempt), self.settings.backoff_max_s
                    )
                    time.sleep(delay + random.uniform(0, delay / 2))
                else:
                    log.warning("llmobs: dropping %d events after retries: %s", len(batch), exc)

        self._consec_failures += 1
        if self._consec_failures >= self.settings.breaker_threshold:
            self._breaker_open_until = time.monotonic() + self.settings.breaker_cooldown_s
            log.warning("llmobs: circuit opened for %.1fs", self.settings.breaker_cooldown_s)
        with self._lock:
            self.stats["dropped_failed"] += len(batch)
        return False
