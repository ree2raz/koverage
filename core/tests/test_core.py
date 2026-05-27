"""No-network unit tests for the shared core: pure logic only."""

from llmcore import CALCULATOR, CLOCK, Memory, Role, cost_usd, get_model
from llmcore.providers.openai_compatible import _to_openai
from llmcore.providers.router import Router
from llmcore.types import Message, ToolCall


def test_calculator_safe_eval():
    assert CALCULATOR.run(expression="2 + 3 * 4") == "14"
    assert CALCULATOR.run(expression="2 ** 10") == "1024"
    # no code execution: names/calls are rejected, not evaluated
    assert "error" in CALCULATOR.run(expression="__import__('os').system('ls')")


def test_clock_returns_iso():
    assert "T" in CLOCK.run()  # ISO-8601 has a 'T' separator


def test_memory_window_and_system_prompt():
    mem = Memory("SYS", max_turns=2)
    for i in range(4):
        mem.add_user(f"u{i}")
    ctx = mem.context()
    assert ctx[0].role is Role.SYSTEM and ctx[0].content == "SYS"
    # only the last 2 turns survive the window
    assert [m.content for m in ctx[1:]] == ["u2", "u3"]


def test_openai_message_conversion_tool_calls():
    msg = Message(
        role=Role.ASSISTANT,
        content="",
        tool_calls=[ToolCall(id="c1", name="calculator", arguments={"expression": "1+1"})],
    )
    out = _to_openai([msg])[0]
    assert out["tool_calls"][0]["function"]["name"] == "calculator"
    assert out["content"] is None  # OpenAI requires null content alongside tool_calls


def test_cost_uses_catalog():
    # GPT-4.1: $2/1M prompt, $8/1M completion -> 1000 in, 1000 out
    c = cost_usd("openai/gpt-4.1", 1000, 1000)
    assert c == round((1000 / 1_000_000) * 2.0 + (1000 / 1_000_000) * 8.0, 6)
    # self-hosted / unknown models cost 0 per token (GPU-time accounted elsewhere)
    assert cost_usd("google/gemma-3n-e4b-it", 1000, 1000) == 0.0
    assert cost_usd("does/not-exist", 10, 10) == 0.0


def test_router_infers_provider_from_unknown_slug():
    r = Router()
    b = r.backend_for("mistralai/mixtral-8x7b")  # not in catalog
    assert b.provider == "mistralai"
    assert b.model == "mistralai/mixtral-8x7b"


def test_catalog_provider_labels():
    assert get_model("openai/gpt-4.1").provider == "openai"
    assert get_model("google/gemma-3n-e4b-it").gateway == "oss"
