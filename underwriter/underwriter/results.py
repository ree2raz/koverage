"""The Scorecard — the single artifact the report (PDF) and the web Evaluation
view both consume."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .scoring import ModelResult


class FrontierPoint(BaseModel):
    model: str
    avg_cost_usd: float
    avg_latency_s: float
    overall_risk: float
    insurability_index: int     # modal linear index (transparency)
    premium_tier: str           # modal linear tier (transparency)
    tail_index: int = 0         # worst-of-k tail index (pricing signal)
    priced_tier: str = ""       # authoritative tier for premium pricing
    binding_constraint: str | None = None  # reason the tier was capped (if any)
    power_warning: bool = False


class GuardrailDelta(BaseModel):
    model: str
    # Modal index delta (transparency — same scale as before).
    index_off: int
    index_on: int
    delta: int  # index_on - index_off (positive = guardrail improved insurability)
    risk_off: float
    risk_on: float
    axis_risk_delta: dict[str, float] = Field(default_factory=dict)  # off - on per axis
    # Priced tier delta (authoritative for Ollive underwriting).
    priced_tier_off: str = ""
    priced_tier_on: str = ""
    tail_index_off: int = 0
    tail_index_on: int = 0
    tail_delta: int = 0  # tail_index_on - tail_index_off


class Scorecard(BaseModel):
    generated_at: str
    mode: str = "live"  # "live" | "synthetic-demo"
    manifest: dict = Field(default_factory=dict)
    cards: list[dict] = Field(default_factory=list)
    axis_weights: dict = Field(default_factory=dict)
    models: list[ModelResult] = Field(default_factory=list)  # every (model, guard) cell
    frontier: list[FrontierPoint] = Field(default_factory=list)  # guard-off, per model
    guardrail_delta: list[GuardrailDelta] = Field(default_factory=list)
