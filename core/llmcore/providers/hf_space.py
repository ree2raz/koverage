"""Backend for HF Space Gradio apps (ZeroGPU OSS model).

Calls the Space's `eval_generate` function via the Gradio client.
The Space returns {"text": str, "latency_s": float, "completion_tokens": int}.

Failure modes we retry through:
  - Client init: ValueError ("Could not fetch config…") when the Space is asleep
    and the /config endpoint hasn't come up yet. Cold-start usually clears within
    30–60s; we retry the Client construction with the same backoff as predict.
  - predict: CancelledError when ZeroGPU sheds load mid-SSE, AppError for
    server-side hiccups, httpx errors for network blips, TimeoutError if the SSE
    stalls. All transient.
"""

from __future__ import annotations

import random
import sys
import time
from collections.abc import Iterator
from concurrent.futures import CancelledError

import httpx
from gradio_client import Client
from gradio_client.exceptions import AppError

from ..types import Message, ModelResponse, Role, StreamPiece, Usage

_TRANSIENT = (CancelledError, AppError, httpx.HTTPError, TimeoutError)
# gradio_client raises a bare ValueError ("Could not fetch config for …") when the
# Space's /config endpoint isn't ready yet — common during cold start.
_TRANSIENT_INIT = _TRANSIENT + (ValueError,)


class HFSpaceBackend:
    """Wraps a Gradio Space that exposes an eval_generate(prompt, system) function."""

    def __init__(
        self,
        space_url: str,
        model_id: str = "oss",
        *,
        max_retries: int = 4,
        retry_base_delay: float = 5.0,
    ) -> None:
        self.space_url = space_url.rstrip("/")
        self.model_id = model_id
        self.provider = "oss"
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._client: Client | None = None

    def _get_client(self) -> Client:
        """Build the Gradio Client, retrying through cold-start config failures."""
        if self._client is not None:
            return self._client
        last_exc: BaseException | None = None
        for attempt in range(self.max_retries):
            try:
                self._client = Client(self.space_url, verbose=False)
                return self._client
            except _TRANSIENT_INIT as exc:
                last_exc = exc
                if attempt == self.max_retries - 1:
                    break
                wait = self.retry_base_delay * (2 ** attempt) + random.uniform(0, 2)
                print(
                    f"  [hf-space] Client init {type(exc).__name__} on attempt "
                    f"{attempt + 1}/{self.max_retries}; sleeping {wait:.1f}s "
                    f"(Space likely cold-starting)",
                    file=sys.stderr,
                )
                time.sleep(wait)
        raise last_exc  # type: ignore[misc]

    def _predict_with_retry(self, prompt: str, system: str) -> object:
        last_exc: BaseException | None = None
        for attempt in range(self.max_retries):
            try:
                return self._get_client().predict(prompt, system, api_name="/eval")
            except _TRANSIENT as exc:
                last_exc = exc
                if attempt == self.max_retries - 1:
                    break
                # exponential backoff with jitter — avoids retry storms across threads
                wait = self.retry_base_delay * (2 ** attempt) + random.uniform(0, 2)
                print(
                    f"  [hf-space] {type(exc).__name__} on attempt {attempt + 1}/"
                    f"{self.max_retries}; sleeping {wait:.1f}s before retry",
                    file=sys.stderr,
                )
                # reset the client on cancellation — the SSE session may be poisoned
                if isinstance(exc, CancelledError):
                    self._client = None
                time.sleep(wait)
        raise last_exc  # type: ignore[misc]

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
        prompt = "\n".join(parts) if len(parts) > 1 else (parts[0].removeprefix("User: ") if parts else "")
        return prompt, system

    def generate(self, messages: list[Message], **kwargs) -> ModelResponse:
        prompt, system = self._messages_to_prompt(messages)
        t0 = time.perf_counter()
        result = self._predict_with_retry(prompt, system)
        latency = time.perf_counter() - t0

        if isinstance(result, dict):
            text = result.get("text", "")
            completion_tokens = result.get("completion_tokens", max(1, len(text) // 4))
            reported_latency = result.get("latency_s", latency)
        else:
            text = str(result)
            completion_tokens = max(1, len(text) // 4)
            reported_latency = latency

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
