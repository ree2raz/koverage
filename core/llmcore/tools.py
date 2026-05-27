"""Tools the assistant can call.

Kept small but real: a safe arithmetic evaluator and a clock. Tool use is part
of the assistant contract and also a risk surface — a model that fabricates
tool results, or calls tools it shouldn't, is a liability Underwriter scores.
"""

from __future__ import annotations

import ast
import datetime as _dt
import operator
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field


class Tool(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)  # JSON schema
    fn: Callable[..., str]

    model_config = {"arbitrary_types_allowed": True}

    def run(self, **kwargs: Any) -> str:
        return self.fn(**kwargs)

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---- safe calculator -------------------------------------------------------

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


def _calculate(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        return str(_safe_eval(tree.body))
    except (ValueError, SyntaxError, ZeroDivisionError) as exc:
        return f"error: {exc}"


def _now(timezone: str = "UTC") -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


CALCULATOR = Tool(
    name="calculator",
    description="Evaluate a basic arithmetic expression (+, -, *, /, **, %).",
    parameters={
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
    },
    fn=_calculate,
)

CLOCK = Tool(
    name="current_datetime",
    description="Return the current UTC date and time in ISO-8601 format.",
    parameters={
        "type": "object",
        "properties": {"timezone": {"type": "string", "default": "UTC"}},
    },
    fn=_now,
)

DEFAULT_TOOLS: list[Tool] = [CALCULATOR, CLOCK]
