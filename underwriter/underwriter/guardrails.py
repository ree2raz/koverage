"""Eval guardrail — wraps llmcore's DefaultGuardrail with the eval-only SENTINEL.

The actual rules (input regex, output PII scrub, harmful-content blocker, and the
optional LLM *semantic* input check) live in llmcore.guardrails so the same layer
can be wired into the Beacon chat gateway. This module adds two eval-specific things:

  1. a confidential token planted in the eval system prompt that the model must
     never echo back (`confidential_tokens=[SENTINEL]`);
  2. a sync bridge to the semantic check. The chat gateway runs the guardrail
     through `check_input_async` (regex → LLM); the eval drives it through
     `Assistant.chat()`, which calls the *synchronous* `check_input`. Without the
     bridge below, passing a backend in would be dead weight and the eval would
     silently credit a weaker, regex-only guardrail than production ships.

Threat to validity — sentinel-match circularity: the guardrail is handed the exact
SENTINEL the output scorer flags, so part of the guard-on uplift is string-match on
a known fixture, not generalisation. A held-out, run-time sentinel would measure the
real effect — see docs/METHODOLOGY.md §11.
"""

from __future__ import annotations

from typing import Any

from llmcore.guardrails import REFUSAL_MESSAGE, DefaultGuardrail  # re-exported

from .datasets import SENTINEL

# Backward-compat alias — Underwriter code historically imported `Guardrail`.
Guardrail = DefaultGuardrail
__all__ = ["Guardrail", "DefaultGuardrail", "REFUSAL_MESSAGE", "build_guardrail"]


class _EvalGuardrail(DefaultGuardrail):
    """DefaultGuardrail whose synchronous `check_input` also runs the LLM semantic
    check when a backend is configured.

    The eval calls the guardrail synchronously (via `Assistant.chat`), so the
    regex-then-semantic gate the gateway gets from `check_input_async` has to be
    reproduced on the sync path. Regex blocks short-circuit before any LLM call,
    and the semantic check fails open on error — matching the async behaviour.
    """

    def check_input(self, text: str) -> tuple[bool, str]:
        ok, msg = super().check_input(text)
        if not ok or self.backend is None:
            return ok, msg
        return self._semantic_check(text)


def build_guardrail(backend: Any = None) -> DefaultGuardrail:
    """Construct the eval guardrail.

    Pass a `backend` (a ModelBackend) to enable the semantic LLM input check — the
    same layer the chat gateway ships. Omit it for regex-only mode (unit tests).
    """
    return _EvalGuardrail(confidential_tokens=[SENTINEL], backend=backend)
