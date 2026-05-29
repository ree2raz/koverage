"""Beacon chat gateway — FastAPI.

Endpoints:
  POST /chat                         SSE token stream (multi-provider, instrumented)
  POST /conversations/{id}/cancel    stop an in-flight stream
  GET  /models                       catalog for the model selector
  GET  /api/...                      read API (conversations, logs, metrics)
  GET  /healthz, /readyz, /metrics   ops
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llmcore import CATALOG
from llmcore.catalog import chat_models
from prometheus_client import Counter, Histogram, make_asgi_app
from sse_starlette.sse import EventSourceResponse

from ..logging_config import configure_logging
from ..settings import settings
from .chat import ChatRequest, chat_stream, request_cancel
from .read import router as read_router

configure_logging()

CHATS = Counter("beacon_chats_total", "Chat turns started", ["model"])
CHAT_LATENCY = Histogram(
    "beacon_chat_latency_seconds",
    "End-to-end chat stream latency",
    ["model"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # tables are created via `python -m beacon.db.init` or alembic


app = FastAPI(title="Beacon Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(read_router)
app.mount("/metrics", make_asgi_app())


@app.post("/chat")
async def chat(req: ChatRequest):
    CHATS.labels(model=req.model or "default").inc()
    return EventSourceResponse(chat_stream(req))


@app.post("/conversations/{convo_id}/cancel")
async def cancel(convo_id: str) -> dict:
    request_cancel(convo_id)
    return {"conversation_id": convo_id, "cancelling": True}


@app.get("/models")
async def models() -> list[dict]:
    return [
        {"id": m.id, "label": m.label, "provider": m.provider, "gateway": m.gateway}
        for m in chat_models()
    ]


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict:
    return {"status": "ready"}
