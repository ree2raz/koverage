"""llmcore — the shared LLM layer for the Ollive platform.

Both modules build on this:
  - Beacon (observability) instruments these backends with its SDK.
  - Underwriter (evaluation) compares models reached through this router.
"""

from .assistant import Assistant, AssistantReply, Guardrail
from .catalog import CATALOG, ModelInfo, get_model, models_for_gateway
from .config import CoreSettings, settings
from .memory import Memory
from .pricing import cost_usd
from .providers import OpenAICompatibleBackend, Router
from .tools import CALCULATOR, CLOCK, DEFAULT_TOOLS, Tool
from .types import Message, ModelBackend, ModelResponse, Role, StreamPiece, ToolCall, Usage

__all__ = [
    "Assistant",
    "AssistantReply",
    "Guardrail",
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
    "cost_usd",
    "OpenAICompatibleBackend",
    "Router",
    "CoreSettings",
    "settings",
]
