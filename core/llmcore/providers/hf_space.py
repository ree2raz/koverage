"""Backend for HF Space Gradio apps (ZeroGPU OSS model).

Calls the Space's `eval_generate` function via the Gradio client.
The Space returns {"text": str, "latency_s": float, "completion_tokens": int}.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

from gradio_client import Client

from ..types import Message, ModelResponse, Role, StreamPiece, Usage


class HFSpaceBackend:
    """Wraps a Gradio Space that exposes an eval_generate(prompt, system) function."""

    def __init__(self, space_url: str, model_id: str = "oss") -> None:
        self.space_url = space_url.rstrip("/")
        self.model_id = model_id
        self.provider = "oss"
        self._client: Client | None = None

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = Client(self.space_url, verbose=False)
        return self._client

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
        result = self._get_client().predict(prompt, system, api_name="/eval")
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
