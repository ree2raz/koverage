"""Shared message / response types and the ModelBackend protocol.

These types are deliberately backend-agnostic. Every model — a frontier model
behind OpenRouter, or a self-hosted OSS model on an HF Space — exchanges the
same Message objects, so the only thing that differs between them is which
ModelBackend is plugged in. That keeps both jobs honest:

- Beacon (observability) instruments one code path regardless of provider.
- Underwriter (evaluation) compares models on identical prompts/memory/tools.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: Role
    content: str = ""
    name: str | None = None  # tool name (for TOOL messages)
    tool_call_id: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ModelResponse(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    latency_s: float = 0.0
    ttft_s: float | None = None  # time-to-first-token (streaming only)
    model: str = ""
    provider: str = ""
    finish_reason: str | None = None


class StreamPiece(BaseModel):
    """One item from a streaming generation: a token delta, or — on the final
    chunk — the usage/finish_reason. Carrying usage in the stream lets callers
    record cost and tokens without a second request."""

    delta: str = ""
    usage: Usage | None = None
    finish_reason: str | None = None


@runtime_checkable
class ModelBackend(Protocol):
    """Minimal contract every model backend implements.

    `provider` is the upstream vendor label (openai / anthropic / google / oss);
    `model` is the concrete model id used on the wire.
    """

    provider: str
    model: str

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        **params: Any,
    ) -> ModelResponse: ...

    def stream(
        self,
        messages: list[Message],
        **params: Any,
    ) -> Iterator[str]: ...
