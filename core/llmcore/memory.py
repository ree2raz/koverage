"""Short-term conversational memory.

Sliding window over recent turns plus an optional rolling summary of older
turns. The summary keeps long conversations within the context budget without
dropping early facts outright — relevant both for chat quality and for the
hallucination axis Underwriter measures (a model that forgets earlier turns
will confabulate).
"""

from __future__ import annotations

from collections.abc import Callable

from .types import Message, Role


class Memory:
    def __init__(
        self,
        system_prompt: str,
        *,
        max_turns: int = 12,
        summarizer: Callable[[list[Message]], str] | None = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self._summarizer = summarizer
        self._history: list[Message] = []
        self._summary: str = ""

    def add(self, message: Message) -> None:
        self._history.append(message)
        self._maybe_summarize()

    def add_user(self, content: str) -> None:
        self.add(Message(role=Role.USER, content=content))

    def add_assistant(self, message: Message) -> None:
        self.add(message)

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        self.add(Message(role=Role.TOOL, tool_call_id=tool_call_id, name=name, content=content))

    @property
    def history(self) -> list[Message]:
        return list(self._history)

    def load(self, messages: list[Message]) -> None:
        """Seed memory from persisted history (used when resuming a conversation)."""
        self._history = list(messages)
        self._maybe_summarize()

    def context(self) -> list[Message]:
        """System prompt (+ rolling summary) followed by the recent window."""
        system = self.system_prompt
        if self._summary:
            system = f"{system}\n\nConversation summary so far:\n{self._summary}"
        window = self._history[-self.max_turns :]
        return [Message(role=Role.SYSTEM, content=system), *window]

    def _maybe_summarize(self) -> None:
        if self._summarizer is None:
            return
        overflow = len(self._history) - self.max_turns
        if overflow > 0:
            older = self._history[:overflow]
            self._summary = self._summarizer(older)
