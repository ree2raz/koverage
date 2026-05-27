"""Read API for the dashboards and trace view.

Analytics run as Postgres aggregates (percentiles via `percentile_cont`, rollups
via `date_trunc`). At take-home volume this is instant; the documented scale-out
path swaps these for ClickHouse rollups behind the same endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import get_session
from . import conversations as convo_repo

router = APIRouter(prefix="/api", tags=["read"])


def _rows(result: Any) -> list[dict]:
    return [dict(r._mapping) for r in result]


@router.get("/conversations")
async def list_conversations(session: AsyncSession = Depends(get_session)) -> list[dict]:
    convos = await convo_repo.list_conversations(session)
    return [
        {
            "id": c.id,
            "title": c.title,
            "status": c.status,
            "default_model": c.default_model,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convos
    ]


@router.get("/conversations/{convo_id}")
async def get_conversation(convo_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    convo = await convo_repo.get_conversation(session, convo_id)
    if convo is None:
        raise HTTPException(404, "conversation not found")
    msgs = await convo_repo.get_messages(session, convo_id)
    return {
        "id": convo.id,
        "title": convo.title,
        "status": convo.status,
        "default_model": convo.default_model,
        "messages": [
            {"id": m.id, "role": m.role, "content": m.content, "sequence": m.sequence,
             "created_at": m.created_at.isoformat() if m.created_at else None}
            for m in msgs
        ],
    }


@router.get("/conversations/{convo_id}/logs")
async def conversation_logs(convo_id: str, session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Inference logs for the trace waterfall: every model call this convo made."""
    result = await session.execute(
        text(
            "SELECT request_id, message_id, provider, model, status, error_type, "
            "latency_ms, ttft_ms, prompt_tokens, completion_tokens, total_tokens, "
            "cost_usd, input_preview, output_preview, redaction_counts, ts "
            "FROM inference_logs WHERE conversation_id = :cid ORDER BY ts"
        ),
        {"cid": convo_id},
    )
    return _rows(result)


@router.get("/logs")
async def recent_logs(limit: int = 50, session: AsyncSession = Depends(get_session)) -> list[dict]:
    result = await session.execute(
        text(
            "SELECT request_id, conversation_id, provider, model, status, latency_ms, "
            "ttft_ms, total_tokens, cost_usd, input_preview, output_preview, "
            "redaction_counts, ts FROM inference_logs ORDER BY ts DESC LIMIT :lim"
        ),
        {"lim": min(limit, 500)},
    )
    return _rows(result)


@router.get("/metrics/summary")
async def metrics_summary(window_minutes: int = 1440, session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Per provider+model: volume, error rate, latency/TTFT percentiles, tokens, cost."""
    result = await session.execute(
        text(
            """
            SELECT provider, model,
                   count(*)                                              AS requests,
                   count(*) FILTER (WHERE status = 'error')              AS errors,
                   count(*) FILTER (WHERE status = 'cancelled')          AS cancelled,
                   percentile_cont(0.5)  WITHIN GROUP (ORDER BY latency_ms) AS p50_ms,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
                   percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99_ms,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY ttft_ms)    AS ttft_p95_ms,
                   sum(total_tokens)                                     AS tokens,
                   round(sum(cost_usd), 6)                               AS cost_usd
            FROM inference_logs
            WHERE ts >= now() - make_interval(mins => :w)
            GROUP BY provider, model
            ORDER BY requests DESC
            """
        ),
        {"w": window_minutes},
    )
    return _rows(result)


@router.get("/metrics/timeseries")
async def metrics_timeseries(window_minutes: int = 60, session: AsyncSession = Depends(get_session)) -> list[dict]:
    """Per-minute buckets for throughput / latency / error / cost charts."""
    result = await session.execute(
        text(
            """
            SELECT date_trunc('minute', ts)                              AS bucket,
                   count(*)                                              AS requests,
                   count(*) FILTER (WHERE status = 'error')              AS errors,
                   percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_ms,
                   sum(total_tokens)                                     AS tokens,
                   round(sum(cost_usd), 6)                               AS cost_usd
            FROM inference_logs
            WHERE ts >= now() - make_interval(mins => :w)
            GROUP BY bucket
            ORDER BY bucket
            """
        ),
        {"w": window_minutes},
    )
    return _rows(result)
