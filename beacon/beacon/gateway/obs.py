"""Process-wide observability client for the gateway.

One ObsClient (one bounded queue + one background flusher) shared by all
requests. Created lazily; flushed on shutdown by the SDK's atexit hook.
"""

from __future__ import annotations

from llmobs import ObsClient

_client: ObsClient | None = None


def get_obs() -> ObsClient:
    global _client
    if _client is None:
        _client = ObsClient()
    return _client
