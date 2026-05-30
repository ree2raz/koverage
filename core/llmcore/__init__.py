"""llmcore: the shared LLM layer for the Koverage platform.

Both modules build on this:
  - Beacon (observability) instruments these backends with its SDK.
  - Underwriter (evaluation) compares models reached through this router.
"""

from .assistant import Assistant, AssistantReply, Guardrail
from .catalog import CATALOG, ModelInfo, chat_models, get_model, models_for_gateway
from .config import CoreSettings, settings
from .guardrails import REFUSAL_MESSAGE, DefaultGuardrail, build_guardrail
from .memory import Memory
from .pricing import cost_usd
from .providers import OpenAICompatibleBackend, Router
from .tools import CALCULATOR, CLOCK, DEFAULT_TOOLS, Tool
from .types import Message, ModelBackend, ModelResponse, Role, StreamPiece, ToolCall, Usage

__all__ = [
    "Assistant",
    "AssistantReply",
    "Guardrail",
    "DefaultGuardrail",
    "REFUSAL_MESSAGE",
    "build_guardrail",
    "Memory",
    "Tool",
    "CALCULATOR",
    "CLOCK",
    "DEFAULT_TOOLS",
    "Message",
    "ModelBackend",
    "ModelResponse",
    "StreamPiece",
    "Role",
    "ToolCall",
    "Usage",
    "CATALOG",
    "ModelInfo",
    "get_model",
    "models_for_gateway",
    "chat_models",
    "cost_usd",
    "OpenAICompatibleBackend",
    "Router",
    "CoreSettings",
    "settings",
]
