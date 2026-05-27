"""The capture ergonomics: a `trace(...)` span that times a call, redacts
previews, and emits one InferenceEvent on exit — success, error, or cancel.

    with obs.trace(conversation_id=cid, provider="openai", model="gpt-4.1") as span:
        span.set_input(user_text)
        for token in backend.stream(...):
            span.mark_first_token()      # records TTFT exactly once
            span.append_output(token)
        span.set_usage(prompt_tokens=..., completion_tokens=..., cost_usd=...)

The event is built and handed to the (non-blocking) client in `finally`, so it
fires whether the body returns, raises, or is cancelled.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from .client import ObsClient
from .redaction import Redactor
from .schema import InferenceEvent, Status


@dataclass
class Span:
    conversation_id: str
    provider: str
    model: str
    session_id: str = ""
    message_id: str = ""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    status: Status = "ok"
    error_type: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    _t0: float = field(default_factory=time.perf_counter)
    _ttft_s: float | None = None
    _input: str = ""
    _output_parts: list[str] = field(default_factory=list)

    def set_input(self, text: str) -> None:
        self._input = text or ""

    def mark_first_token(self) -> None:
        if self._ttft_s is None:
            self._ttft_s = time.perf_counter() - self._t0

    def append_output(self, chunk: str) -> None:
        self._output_parts.append(chunk)

    def set_output(self, text: str) -> None:
        self._output_parts = [text]

    def set_usage(
        self, *, prompt_tokens: int = 0, completion_tokens: int = 0, cost_usd: float = 0.0
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.cost_usd = cost_usd

    def set_status(self, status: Status, error_type: str = "") -> None:
        self.status = status
        self.error_type = error_type


@contextmanager
def trace(
    client: ObsClient,
    *,
    conversation_id: str,
    provider: str,
    model: str,
    session_id: str = "",
    message_id: str = "",
    redactor: Redactor | None = None,
    preview_chars: int | None = None,
) -> Iterator[Span]:
    span = Span(
        conversation_id=conversation_id,
        provider=provider,
        model=model,
        session_id=session_id,
        message_id=message_id,
    )
    red = redactor or Redactor()
    limit = preview_chars if preview_chars is not None else client.settings.preview_chars
    try:
        yield span
    except BaseException as exc:  # includes asyncio.CancelledError
        name = type(exc).__name__
        span.set_status("cancelled" if name == "CancelledError" else "error", name)
        raise
    finally:
        latency_ms = int((time.perf_counter() - span._t0) * 1000)
        ttft_ms = int(span._ttft_s * 1000) if span._ttft_s is not None else 0

        in_red, in_counts = red.redact(span._input)
        out_red, out_counts = red.redact("".join(span._output_parts))
        counts = {k: in_counts.get(k, 0) + out_counts.get(k, 0)
                  for k in set(in_counts) | set(out_counts)}

        event = InferenceEvent(
            request_id=span.request_id,
            conversation_id=span.conversation_id,
            message_id=span.message_id,
            session_id=span.session_id,
            provider=span.provider,
            model=span.model,
            status=span.status,
            error_type=span.error_type,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            prompt_tokens=span.prompt_tokens,
            completion_tokens=span.completion_tokens,
            total_tokens=span.prompt_tokens + span.completion_tokens,
            cost_usd=span.cost_usd,
            input_preview=in_red[:limit],
            output_preview=out_red[:limit],
            redaction_counts=counts,
            meta=span.meta,
        )
        client.emit(event)
