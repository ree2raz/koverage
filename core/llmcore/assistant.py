"""The Assistant orchestrator.

Ties a ModelBackend to memory, tools, a system prompt, and (optionally) a
guardrail layer. The same Assistant class drives every backend — so any
behavioural difference Underwriter measures comes from the model, not from
divergent scaffolding.

Guardrails are injected, not baked in, so the eval harness can run the exact
same assistant with guardrails on and off and attribute the risk delta to the
guardrail layer alone.
"""

from __future__ import annotations

from typing import Any, Protocol

from .memory import Memory
from .tools import Tool
from .types import Message, ModelBackend, ModelResponse, Role


class Guardrail(Protocol):
    def check_input(self, text: str) -> tuple[bool, str]:
        """Return (allowed, replacement_or_reason)."""
        ...

    def check_output(self, text: str) -> tuple[bool, str]:
        """Return (allowed, safe_text_or_reason)."""
        ...


class AssistantReply:
    def __init__(
        self,
        text: str,
        *,
        responses: list[ModelResponse],
        blocked_by: str | None = None,
    ) -> None:
        self.text = text
        self.responses = responses  # every model round-trip this turn
        self.blocked_by = blocked_by  # guardrail stage that intervened, if any

    @property
    def latency_s(self) -> float:
        return sum(r.latency_s for r in self.responses)

    @property
    def total_tokens(self) -> int:
        return sum(r.usage.total_tokens for r in self.responses)


class Assistant:
    def __init__(
        self,
        backend: ModelBackend,
        memory: Memory,
        *,
        tools: list[Tool] | None = None,
        guardrail: Guardrail | None = None,
        max_tool_hops: int = 4,
        gen_params: dict[str, Any] | None = None,
    ) -> None:
        self.backend = backend
        self.memory = memory
        self.tools = tools or []
        self.guardrail = guardrail
        self.max_tool_hops = max_tool_hops
        self.gen_params = gen_params or {}
        self._tool_map = {t.name: t for t in self.tools}

    def chat(self, user_input: str) -> AssistantReply:
        if self.guardrail:
            allowed, reason = self.guardrail.check_input(user_input)
            if not allowed:
                return AssistantReply(reason, responses=[], blocked_by="input")

        self.memory.add_user(user_input)
        responses: list[ModelResponse] = []
        tool_schemas = [t.to_openai() for t in self.tools] or None

        for _ in range(self.max_tool_hops + 1):
            resp = self.backend.generate(
                self.memory.context(), tools=tool_schemas, **self.gen_params
            )
            responses.append(resp)

            if not resp.tool_calls:
                break

            # record the assistant's tool-call turn, then execute each call
            self.memory.add_assistant(
                Message(role=Role.ASSISTANT, content=resp.text, tool_calls=resp.tool_calls)
            )
            for call in resp.tool_calls:
                tool = self._tool_map.get(call.name)
                result = tool.run(**call.arguments) if tool else f"error: unknown tool {call.name}"
                self.memory.add_tool_result(call.id, call.name, result)
        else:
            # loop exhausted without a final answer
            text = responses[-1].text or "(stopped: tool-hop limit reached)"
            self.memory.add_assistant(Message(role=Role.ASSISTANT, content=text))
            return AssistantReply(text, responses=responses, blocked_by="tool_limit")

        text = responses[-1].text
        if self.guardrail:
            allowed, safe = self.guardrail.check_output(text)
            text = safe
            if not allowed:
                self.memory.add_assistant(Message(role=Role.ASSISTANT, content=text))
                return AssistantReply(text, responses=responses, blocked_by="output")

        self.memory.add_assistant(Message(role=Role.ASSISTANT, content=text))
        return AssistantReply(text, responses=responses)
