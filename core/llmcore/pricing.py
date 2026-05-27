"""Cost attribution. Turns token usage into USD using the catalog.

Centralised so Beacon (per-request cost in the dashboard) and Underwriter (the
cost axis of the cost x latency x risk tradeoff) compute money the same way.
"""

from __future__ import annotations

from .catalog import get_model


def cost_usd(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    """USD cost of one inference call. Unknown / self-hosted models return 0.0
    (their cost is GPU-time, accounted separately)."""
    info = get_model(model_id)
    if info is None:
        return 0.0
    prompt_cost = (prompt_tokens / 1_000_000) * info.prompt_usd_per_1m
    completion_cost = (completion_tokens / 1_000_000) * info.completion_usd_per_1m
    return round(prompt_cost + completion_cost, 6)
