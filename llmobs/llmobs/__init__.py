"""llmobs — a lightweight, drop-in LLM observability SDK.

Wrap any LLM call in a `trace(...)` span; the SDK captures latency, TTFT, token
usage, cost, status, and redacted previews, then ships them to an ingestion
endpoint without ever blocking or breaking the call.

    from llmobs import ObsClient, trace

    obs = ObsClient()
    with trace(obs, conversation_id="c1", provider="openai", model="gpt-4.1") as span:
        span.set_input(prompt)
        ...
"""

from .client import HTTPTransport, ObsClient, Transport
from .config import SDKSettings
from .redaction import DEFAULT_PATTERNS, Redactor, redact
from .schema import IngestBatch, InferenceEvent
from .tracer import Span, trace

__all__ = [
    "ObsClient",
    "Transport",
    "HTTPTransport",
    "SDKSettings",
    "Redactor",
    "redact",
    "DEFAULT_PATTERNS",
    "InferenceEvent",
    "IngestBatch",
    "Span",
    "trace",
]
