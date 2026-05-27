"""Underwriter — an LLM evaluation harness framed as AI insurability scoring.

Scores models on hallucination, bias & harmful output, content safety, and
sensitive-data disclosure using deterministic signals + dual cross-provider
judges, then prices an Insurability Index and premium tier.
"""

from .config import AXES, AXIS_LABELS, axis_weights, settings
from .datasets import EVAL_SYSTEM_PROMPT, SENTINEL, load_cards, load_suites
from .guardrails import Guardrail, build_guardrail
from .results import Scorecard
from .runner import run

__all__ = [
    "AXES",
    "AXIS_LABELS",
    "axis_weights",
    "settings",
    "EVAL_SYSTEM_PROMPT",
    "SENTINEL",
    "load_cards",
    "load_suites",
    "Guardrail",
    "build_guardrail",
    "Scorecard",
    "run",
]
