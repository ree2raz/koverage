"""Backend for the Modal-hosted OSS model.

POSTs {"prompt", "system"} to a Modal FastAPI endpoint and expects
{"text", "latency_s", "completion_tokens"} back — same contract as the HF
Space, just a different transport (httpx instead of gradio_client).

Modal is dramatically more reliable than ZeroGPU for live demos: 8–15 s cold
start vs 30–60 s, no shared-GPU load-shedding (i.e. no CancelledError
storms), and `scaledown_window` keeps the container warm across requests.
"""

from __future__ import annotations

import logging
import random
import sys
import time
from collections.abc import Iterator

import httpx

log = logging.getLogger(__name__)

from ..types import Message, ModelResponse, Role, StreamPiece, Usage

_TRANSIENT = (httpx.HTTPError, TimeoutError)


class ModalBackend:
    """Wraps a Modal @fastapi_endpoint that accepts {prompt, system}."""

    def __init__(
        self,
        endpoint_url: str,
        model_id: str = "oss",
        *,
        max_retries: int = 3,
        retry_base_delay: float = 4.0,
        request_timeout: float = 120.0,
    ) -> None:
        self.endpoint_url = endpoint_url.rstrip("/")
        self.model_id = model_id
        self.model = model_id  # satisfies ModelBackend.model protocol attribute
        self.provider = "oss"
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        # cold-start can take ~15s; warm requests sub-2s. 120s covers both with
        # plenty of headroom for max_new_tokens=512 generations.
        self._client = httpx.Client(timeout=request_timeout)

    def _messages_to_prompt(self, messages: list[Message]) -> tuple[str, str]:
        system = ""
        parts: list[str] = []
        for m in messages:
            if m.role is Role.SYSTEM:
                system = m.content or ""
            elif m.role is Role.USER:
                parts.append(f"User: {m.content}")
            elif m.role is Role.ASSISTANT:
                parts.append(f"Assistant: {m.content}")
        prompt = "\n".join(parts) if len(parts) > 1 else (
            parts[0].removeprefix("User: ") if parts else ""
        )
        return prompt, system

    def _post_with_retry(self, prompt: str, system: str) -> dict:
        last_exc: BaseException | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self._client.post(
                    self.endpoint_url, json={"prompt": prompt, "system": system}
                )
                resp.raise_for_status()
                return resp.json()
            except _TRANSIENT as exc:
                last_exc = exc
                if attempt == self.max_retries - 1:
                    break
                wait = self.retry_base_delay * (2 ** attempt) + random.uniform(0, 2)
                print(
                    f"  [modal] {type(exc).__name__} on attempt {attempt + 1}/"
                    f"{self.max_retries}; sleeping {wait:.1f}s before retry",
                    file=sys.stderr,
                )
                time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    def generate(self, messages: list[Message], **kwargs) -> ModelResponse:
        if "response_format" in kwargs:
            log.debug(
                "ModalBackend ignores response_format — JSON mode unsupported; "
                "judge parser will use regex fallback"
            )
        prompt, system = self._messages_to_prompt(messages)
        t0 = time.perf_counter()
        result = self._post_with_retry(prompt, system)
        latency = time.perf_counter() - t0

        text = result.get("text", "")
        completion_tokens = int(
            result.get("completion_tokens", max(1, len(text) // 4))
        )
        reported_latency = float(result.get("latency_s", latency))

        return ModelResponse(
            text=text,
            usage=Usage(
                prompt_tokens=max(1, len(prompt) // 4),
                completion_tokens=completion_tokens,
            ),
            latency_s=reported_latency,
            responses=[],
        )

    def stream_events(self, messages: list[Message], **kwargs) -> Iterator[StreamPiece]:
        response = self.generate(messages, **kwargs)
        yield StreamPiece(delta=response.text, usage=response.usage)
