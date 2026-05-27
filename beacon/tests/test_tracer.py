"""The tracer builds one redacted, timed event per span — on success and error."""

from __future__ import annotations

from llmobs import SDKSettings, trace
from llmobs.schema import InferenceEvent


class FakeObs:
    def __init__(self) -> None:
        self.settings = SDKSettings()
        self.emitted: list[InferenceEvent] = []

    def emit(self, event: InferenceEvent) -> None:
        self.emitted.append(event)


def test_span_emits_redacted_timed_event():
    obs = FakeObs()
    with trace(obs, conversation_id="c1", provider="openai", model="gpt-4.1") as span:
        span.set_input("contact me at user@example.com")
        span.mark_first_token()
        span.append_output("sure, your data is safe")
        span.set_usage(prompt_tokens=10, completion_tokens=7, cost_usd=0.001)

    assert len(obs.emitted) == 1
    ev = obs.emitted[0]
    assert ev.status == "ok"
    assert ev.provider == "openai" and ev.model == "gpt-4.1"
    assert "user@example.com" not in ev.input_preview  # redacted before egress
    assert ev.redaction_counts.get("email") == 1
    assert ev.total_tokens == 17
    assert ev.ttft_ms >= 0 and ev.latency_ms >= 0


def test_span_records_errors():
    obs = FakeObs()
    try:
        with trace(obs, conversation_id="c1", provider="openai", model="gpt-4.1") as span:
            span.set_input("hello")
            raise ValueError("boom")
    except ValueError:
        pass

    assert len(obs.emitted) == 1
    assert obs.emitted[0].status == "error"
    assert obs.emitted[0].error_type == "ValueError"
