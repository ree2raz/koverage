"""One backend for every hosted model.

OpenRouter, OpenAI, vLLM — they all speak the OpenAI Chat Completions API, so a
single client covers them; they differ only by base_url / api_key / model. This
is what keeps the comparison honest and the instrumentation uniform: identical
request shape, only the endpoint changes.

`stream()` measures time-to-first-token (TTFT) — the latency that actually
matters for chat UX and a signal most basic loggers miss.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from ..types import Message, ModelResponse, Role, StreamPiece, ToolCall, Usage


def _to_openai(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        d: dict[str, Any] = {"role": m.role.value, "content": m.content}
        if m.role is Role.TOOL:
            d["tool_call_id"] = m.tool_call_id
        if m.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in m.tool_calls
            ]
            # OpenAI requires content to be null when tool_calls are present
            d["content"] = m.content or None
        out.append(d)
    return out


def _loads(s: str) -> dict[str, Any]:
    try:
        return json.loads(s) if s else {}
    except json.JSONDecodeError:
        return {}


class OpenAICompatibleBackend:
    """Implements the ModelBackend protocol over any OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        base_url: str,
        api_key: str,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key or "EMPTY",
            default_headers=default_headers or None,
        )

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **params: Any,
    ) -> ModelResponse:
        kwargs: dict[str, Any] = {"model": self.model, "messages": _to_openai(messages)}
        if tools:
            kwargs["tools"] = tools
        kwargs.update(params)

        t0 = time.perf_counter()
        resp = self._client.chat.completions.create(**kwargs)
        latency = time.perf_counter() - t0

        choice = resp.choices[0]
        msg = choice.message
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=_loads(tc.function.arguments))
            for tc in (msg.tool_calls or [])
        ]

        usage = Usage()
        if resp.usage:
            usage = Usage(
                prompt_tokens=resp.usage.prompt_tokens or 0,
                completion_tokens=resp.usage.completion_tokens or 0,
            )

        return ModelResponse(
            text=msg.content or "",
            tool_calls=tool_calls,
            usage=usage,
            latency_s=latency,
            model=self.model,
            provider=self.provider,
            finish_reason=choice.finish_reason,
        )

    def stream(self, messages: list[Message], **params: Any) -> Iterator[str]:
        """Plain token stream (content deltas only)."""
        for piece in self.stream_events(messages, **params):
            if piece.delta:
                yield piece.delta

    def stream_events(self, messages: list[Message], **params: Any) -> Iterator[StreamPiece]:
        """Token deltas followed by a final piece carrying usage + finish_reason.

        Requests `stream_options.include_usage` so the last chunk reports tokens;
        gateways need that to attribute cost without a second call.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": _to_openai(messages),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        kwargs.update(params)
        for chunk in self._client.chat.completions.create(**kwargs):
            if chunk.usage:
                yield StreamPiece(
                    usage=Usage(
                        prompt_tokens=chunk.usage.prompt_tokens or 0,
                        completion_tokens=chunk.usage.completion_tokens or 0,
                    )
                )
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.delta and choice.delta.content:
                yield StreamPiece(delta=choice.delta.content)
            if choice.finish_reason:
                yield StreamPiece(finish_reason=choice.finish_reason)
