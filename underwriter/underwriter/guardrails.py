"""Eval guardrail — wraps llmcore's DefaultGuardrail with the eval-only SENTINEL.

The actual rules (input regex, output PII scrub, harmful-content blocker) live in
llmcore.guardrails so the same layer can be wired into the Beacon chat gateway.
This module adds only what's eval-specific: a confidential token planted in the
eval system prompt that the model must never echo back.
"""

from __future__ import annotations

from llmcore.guardrails import REFUSAL_MESSAGE, DefaultGuardrail  # re-exported

from .datasets import SENTINEL

# Backward-compat alias — Underwriter code historically imported `Guardrail`.
Guardrail = DefaultGuardrail
__all__ = ["Guardrail", "DefaultGuardrail", "REFUSAL_MESSAGE", "build_guardrail"]


def build_guardrail() -> DefaultGuardrail:
    return DefaultGuardrail(confidential_tokens=[SENTINEL])
