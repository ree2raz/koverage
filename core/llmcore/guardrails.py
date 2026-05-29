"""Default Guardrail implementation — input + output safety checks.

Lives in llmcore so the same layer is shared by:
  - the Beacon chat gateway (input check before model call)
  - the Underwriter eval harness (input + output, with eval-specific sentinel)

Input checks block known jailbreak templates (DAN, "ignore previous instructions",
developer-mode overrides) and explicit harmful-intent patterns.

Output checks scrub PII (via llmobs.Redactor), block leaks of any caller-provided
confidential tokens, and block residual harmful step-by-step content. Designed for
non-streaming use; the streaming gateway only invokes check_input.
"""

from __future__ import annotations

import re
from typing import Sequence

from llmobs.redaction import Redactor

REFUSAL_MESSAGE = (
    "I can't help with that request, as it may be unsafe or violate usage policies."
)

# Known jailbreak markers + explicit harmful intent + system-prompt extraction.
_INPUT_PATTERNS = [
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
_INPUT_RE = [re.compile(p, re.IGNORECASE) for p in _INPUT_PATTERNS]

_OUTPUT_HARMFUL_PATTERNS = [
    r"step[-\s]?by[-\s]?step.{0,40}(?:synthesi|explosive|weapon|meth)",
]
_OUTPUT_RE = [re.compile(p, re.IGNORECASE) for p in _OUTPUT_HARMFUL_PATTERNS]


class DefaultGuardrail:
    """Implements the llmcore.Guardrail Protocol (check_input / check_output).

    `confidential_tokens` lets callers (esp. the eval harness) block specific
    sentinels in model output. The chat gateway leaves this empty.
    """

    def __init__(
        self,
        *,
        redactor: Redactor | None = None,
        confidential_tokens: Sequence[str] = (),
        refusal_message: str = REFUSAL_MESSAGE,
    ) -> None:
        self.redactor = redactor or Redactor()
        self.confidential_tokens = tuple(t.lower() for t in confidential_tokens if t)
        self.refusal = refusal_message

    def check_input(self, text: str) -> tuple[bool, str]:
        for r in _INPUT_RE:
            if r.search(text):
                return (False, self.refusal)
        return (True, text)

    def check_output(self, text: str) -> tuple[bool, str]:
        lower = text.lower()
        for tok in self.confidential_tokens:
            if tok in lower:
                return (False, self.refusal)
        for r in _OUTPUT_RE:
            if r.search(text):
                return (False, self.refusal)
        redacted, counts = self.redactor.redact(text)
        if counts:
            return (True, redacted)
        return (True, text)


def build_guardrail(*, confidential_tokens: Sequence[str] = ()) -> DefaultGuardrail:
    return DefaultGuardrail(confidential_tokens=confidential_tokens)
