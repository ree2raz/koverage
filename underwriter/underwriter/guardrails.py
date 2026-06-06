"""Eval guardrail — wraps llmcore's DefaultGuardrail for the eval harness.

The actual rules (input regex, output PII scrub, harmful-content blocker, and the
optional LLM *semantic* input check) live in llmcore.guardrails so the same layer
can be wired into the Beacon chat gateway. This module adds an eval-specific sync
bridge to the semantic check. The chat gateway runs the guardrail through
`check_input_async` (regex → LLM); the eval drives it through `Assistant.chat()`,
which calls the *synchronous* `check_input`. Without the bridge below, passing a
backend in would be dead weight and the eval would silently credit a weaker,
regex-only guardrail than production ships.

Fix D (held-out sentinel): The guardrail no longer receives the planted sentinel in
`confidential_tokens`. The run-time sentinel is generated fresh each run via
`new_sentinel()` and is known only to the eval system prompt and the scorer. This
means the guard-on uplift on the sensitive axis now measures genuine generalisation
(semantic/regex pattern detection) rather than string-match on a known fixture.
The real Beacon gateway can still pass `confidential_tokens` when constructing its
own guardrail — that use case is unaffected.
"""

from __future__ import annotations

from typing import Any

from llmcore.guardrails import REFUSAL_MESSAGE, DefaultGuardrail  # re-exported

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

    The guardrail intentionally carries NO `confidential_tokens`: the run-time
    sentinel is withheld from the guardrail so the delta between guard-on and
    guard-off on the sensitive axis measures real pattern generalisation, not
    fixture string-match. This resolves the sentinel-match circularity documented
    in the previous version of this module.
    """
    return _EvalGuardrail(backend=backend)
