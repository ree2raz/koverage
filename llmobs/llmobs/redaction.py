"""PII redaction — runs in-process, before anything is buffered or transmitted.

Privacy by construction: raw PII never reaches the queue, the wire, or the
store. We redact *and* count, so every event carries a receipt of what was
scrubbed (useful for audits and for proving the control works).

Regex-based and dependency-free by default; the pattern set is configurable so
a heavier engine (e.g. Presidio) can be swapped in without touching callers.
"""

from __future__ import annotations

import re

# Order matters: match the most specific / longest tokens first so a credit
# card isn't partially eaten by the phone pattern, etc.
DEFAULT_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?\d{1,3}[ -]?)?(?:\(?\d{3}\)?[ -]?)\d{3}[ -]?\d{4}(?!\d)"),
    "api_key": re.compile(r"\b(?:sk|pk|ghp|gho|xoxb|AKIA)[-_A-Za-z0-9]{12,}\b"),
}

_PLACEHOLDER = "[REDACTED:{}]"


def _luhn(digits: str) -> bool:
    """Return True if `digits` (stripped of non-numeric characters) passes the Luhn checksum."""
    s = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        s += n
    return s % 10 == 0


# Per-pattern validators: match is only redacted when the validator returns True.
_VALIDATORS: dict[str, object] = {
    "credit_card": lambda raw: _luhn(re.sub(r"\D", "", raw)),
}


class Redactor:
    def __init__(self, patterns: dict[str, re.Pattern[str]] | None = None) -> None:
        self.patterns = patterns if patterns is not None else DEFAULT_PATTERNS

    def redact(self, text: str) -> tuple[str, dict[str, int]]:
        """Return (redacted_text, {kind: count}). Empty counts == nothing found."""
        counts: dict[str, int] = {}
        if not text:
            return text, counts
        out = text
        for kind, pattern in self.patterns.items():
            validator = _VALIDATORS.get(kind)
            if validator:
                n = 0

                def _replace(m: re.Match, _kind: str = kind, _val=validator) -> str:
                    nonlocal n
                    if _val(m.group(0)):
                        n += 1
                        return _PLACEHOLDER.format(_kind)
                    return m.group(0)

                out = pattern.sub(_replace, out)
            else:
                out, n = pattern.subn(_PLACEHOLDER.format(kind), out)
            if n:
                counts[kind] = n
        return out, counts


_default = Redactor()


def redact(text: str) -> tuple[str, dict[str, int]]:
    return _default.redact(text)
