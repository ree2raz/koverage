"""The streaming chat path.

Flow per turn:
  1. load/create conversation, persist the user message (synchronous, exact);
  2. rebuild short-term memory from stored history;
  3. stream the model's tokens to the client over SSE;
  4. on completion (or cancel/error) persist the assistant message and emit ONE
     observability event via the SDK — non-blocking, so telemetry never slows
     the token stream.

The model's blocking stream runs in a worker thread and is bridged to async, so
one slow generation never stalls the event loop / other chats.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

from llmcore import Memory, Router, StreamPiece, cost_usd
from llmcore.guardrails import build_guardrail
from llmcore.types import Message as CoreMessage
from llmcore.types import Role
from llmobs import trace
from pydantic import BaseModel

from ..db.base import SessionLocal
from ..settings import settings as beacon_settings
from . import conversations as convo_repo
from .obs import get_obs

log = logging.getLogger("beacon.gateway")

SYSTEM_PROMPT = (
    "You are a helpful, honest, and careful assistant. Hold a natural multi-turn "
    "conversation and remember what the user told you earlier. If unsure of a fact, "
    "say so rather than guessing."
)

_router = Router()

# Explicit-cancel registry: conversation ids the user asked to stop.
_cancelled: set[str] = set()
_cancel_lock = threading.Lock()


def request_cancel(conversation_id: str) -> None:
    with _cancel_lock:
        _cancelled.add(conversation_id)


def _take_cancel(conversation_id: str) -> bool:
    with _cancel_lock:
        if conversation_id in _cancelled:
            _cancelled.discard(conversation_id)
            return True
    return False


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    model: str = ""
    session_id: str = ""
    guardrails_enabled: bool = True


_guardrail = build_guardrail(backend=_router.backend_for(beacon_settings.guardrail_model))


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)  # rough fallback when the API omits usage


async def _aiter_sync(gen_factory: Callable[[], Iterator[StreamPiece]]) -> AsyncIterator[StreamPiece]:
    """Bridge a blocking generator to async via a thread + queue.

    Sets a stop event on cancellation so the worker exits at the next
    iteration boundary instead of consuming the full backend stream.
    """
    loop = asyncio.get_running_loop()
    q: asyncio.Queue[Any] = asyncio.Queue()
    sentinel = object()
    stop = threading.Event()

    def worker() -> None:
        try:
            for item in gen_factory():
                if stop.is_set():
                    break
                loop.call_soon_threadsafe(q.put_nowait, item)
        except Exception as exc:
            if not stop.is_set():
                loop.call_soon_threadsafe(q.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(q.put_nowait, sentinel)

    threading.Thread(target=worker, daemon=True).start()
    try:
        while True:
            item = await q.get()
            if item is sentinel:
                return
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        stop.set()


def _sse(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data)}


async def chat_stream(req: ChatRequest) -> AsyncIterator[dict]:
    model = req.model or _router.settings.default_model
    obs = get_obs()

    if not _router.settings.openrouter_api_key:
        yield _sse("error", {"detail": "OPENROUTER_API_KEY is not set — add it to .env and restart"})
        return

    try:
        # ── Window 1: conversation setup + user message ────────────────────────
        # Session is only held for the two fast DB operations; connection is
        # returned to the pool before the multi-second streaming generation.
        async with SessionLocal() as session:
            if req.conversation_id:
                convo = await convo_repo.get_conversation(session, req.conversation_id)
                if convo is None:
                    yield _sse("error", {"detail": "conversation not found"})
                    return
                if convo.status != "active":
                    await convo_repo.set_status(session, convo.id, "active")
            else:
                title = req.message[:60] or "New conversation"
                convo = await convo_repo.create_conversation(
                    session, model=model, session_id=req.session_id, title=title
                )
            history = await convo_repo.get_messages(session, convo.id)
            await convo_repo.add_message(session, convo_id=convo.id, role="user", content=req.message)
            convo_id = convo.id
            history_messages = [CoreMessage(role=Role(m.role), content=m.content) for m in history]
        # connection returned to pool here

        yield _sse("meta", {"conversation_id": convo_id, "model": model})

        # ── Guardrail: regex fast path + async semantic LLM check ─────────────
        if req.guardrails_enabled:
            allowed, refusal = await _guardrail.check_input_async(req.message)
            if not allowed:
                provider = model.split("/")[0] if "/" in model else model
                with trace(obs, conversation_id=convo_id, provider=provider,
                           model=model, session_id=req.session_id) as span:
                    span.set_input(req.message)
                    span.set_output(refusal)
                    span.set_status("refused", "guardrail_input_block")
                    span.set_usage(prompt_tokens=_approx_tokens(req.message),
                                   completion_tokens=_approx_tokens(refusal), cost_usd=0.0)
                yield _sse("token", {"text": refusal})
                async with SessionLocal() as session:
                    await convo_repo.add_message(
                        session, convo_id=convo_id, role="assistant", content=refusal,
                        token_count=_approx_tokens(refusal),
                    )
                yield _sse("done", {
                    "conversation_id": convo_id, "status": "refused",
                    "prompt_tokens": _approx_tokens(req.message),
                    "completion_tokens": _approx_tokens(refusal),
                    "cost_usd": 0.0, "request_id": span.request_id,
                })
                return

        # ── Memory ────────────────────────────────────────────────────────────
        mem = Memory(SYSTEM_PROMPT)
        mem.load(history_messages)
        mem.add_user(req.message)

        # ── Stream ────────────────────────────────────────────────────────────
        backend = _router.backend_for(model)
        provider = backend.provider
        parts: list[str] = []
        usage = None
        status = "ok"

        def gen() -> Iterator[StreamPiece]:
            return backend.stream_events(mem.context(), temperature=_router.settings.temperature,
                                         max_tokens=_router.settings.max_tokens)

        with trace(obs, conversation_id=convo_id, provider=provider, model=model,
                   session_id=req.session_id) as span:
            span.set_input(req.message)
            try:
                async for piece in _aiter_sync(gen):
                    if _take_cancel(convo_id):
                        status = "cancelled"
                        break
                    if piece.delta:
                        span.mark_first_token()
                        parts.append(piece.delta)
                        yield _sse("token", {"text": piece.delta})
                    if piece.usage:
                        usage = piece.usage
            except Exception as exc:  # noqa: BLE001
                status = "error"
                span.set_status("error", type(exc).__name__)
                yield _sse("error", {"detail": str(exc)})

            text = "".join(parts)
            prompt_tokens = usage.prompt_tokens if usage else _approx_tokens(req.message)
            completion_tokens = usage.completion_tokens if usage else _approx_tokens(text)
            cost = cost_usd(model, prompt_tokens, completion_tokens)
            span.set_status(status)
            span.set_usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, cost_usd=cost)
            span.set_output(text)

        # ── Window 2: persist assistant response ──────────────────────────────
        async with SessionLocal() as session:
            if text:
                await convo_repo.add_message(
                    session, convo_id=convo_id, role="assistant", content=text,
                    token_count=completion_tokens,
                )
            if status == "cancelled":
                await convo_repo.set_status(session, convo_id, "active")

        yield _sse("done", {
            "conversation_id": convo_id,
            "status": status,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost,
            "request_id": span.request_id,
        })
    except Exception as exc:  # noqa: BLE001 — surface setup/DB errors to the UI
        log.exception("unhandled error in chat_stream: %s", exc)
        yield _sse("error", {"detail": f"{type(exc).__name__}: {exc}"})
