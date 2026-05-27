"""A toggleable input/output guardrail implementing the llmcore Guardrail
protocol.

It is *injected* into the assistant, so the eval runs the identical model with
the guardrail on and off and attributes the risk delta to the guardrail alone
(the insurer's "what does a safety layer buy you" question). It deliberately
trades a little over-refusal for much less harmful compliance and leakage — and
the eval measures exactly that tradeoff.

Reuses Beacon's PII redactor for output scrubbing: one privacy control, shared.
"""

from __future__ import annotations

import re

from llmobs.redaction import Redactor

from .datasets import SENTINEL

_REFUSAL = (
    "I can't help with that request, as it may be unsafe or violate usage policies."
)

# Input: known jailbreak markers + explicit harmful intent + disclosure attempts.
_INPUT_BLOCK = [
    r"\bDAN\b|\bdo anything now\b",
    r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
    r"\bdeveloper\s+mode\b|\bno\s+restrictions\b|\bwithout\s+any\s+(?:filter|restriction)",
    r"\bjailbreak\b",
    r"(?:synthesi[sz]e|make|build|produce|manufacture|create|brew)\b.{0,40}"
    r"(?:nerve\s+agent|explosive|bomb|meth|methamphetamine|napalm|chlorine\s+gas|"
    r"ransomware|malware|nuclear|weapon|toxin)",
    r"(?:reveal|print|dump|show)\b.{0,40}(?:system\s+prompt|confidential\s+token|"
    r"instructions|configuration)",
    r"\bsystem\s+override\b",
]
_INPUT_RE = [re.compile(p, re.IGNORECASE) for p in _INPUT_BLOCK]

_OUTPUT_HARMFUL = [
    r"step[-\s]?by[-\s]?step.{0,40}(?:synthesi|explosive|weapon|meth)",
]
_OUTPUT_RE = [re.compile(p, re.IGNORECASE) for p in _OUTPUT_HARMFUL]


class Guardrail:
    """Implements llmcore.Guardrail (check_input / check_output)."""

    def __init__(self, *, redactor: Redactor | None = None) -> None:
        self.redactor = redactor or Redactor()

    def check_input(self, text: str) -> tuple[bool, str]:
        for r in _INPUT_RE:
            if r.search(text):
                return (False, _REFUSAL)
        return (True, text)

    def check_output(self, text: str) -> tuple[bool, str]:
        # 1. confidential-token leak → block outright
        if SENTINEL.lower() in text.lower():
            return (False, _REFUSAL)
        # 2. explicit harmful content slipped through → block
        for r in _OUTPUT_RE:
            if r.search(text):
                return (False, _REFUSAL)
        # 3. scrub any PII before it leaves (privacy by construction)
        redacted, counts = self.redactor.redact(text)
        if counts:
            return (True, redacted)
        return (True, text)


def build_guardrail() -> Guardrail:
    return Guardrail()
