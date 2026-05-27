"""Conversation + message persistence (the synchronous, must-be-correct path)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Conversation, Message


def _uuid() -> str:
    return str(uuid.uuid4())


async def create_conversation(
    session: AsyncSession, *, model: str, session_id: str = "", title: str = "New conversation"
) -> Conversation:
    convo = Conversation(id=_uuid(), session_id=session_id, title=title, default_model=model)
    session.add(convo)
    await session.commit()
    await session.refresh(convo)
    return convo


async def get_conversation(session: AsyncSession, convo_id: str) -> Conversation | None:
    return await session.get(Conversation, convo_id)


async def list_conversations(
    session: AsyncSession, *, session_id: str | None = None, limit: int = 100
) -> list[Conversation]:
    stmt = select(Conversation).order_by(Conversation.updated_at.desc()).limit(limit)
    if session_id:
        stmt = stmt.where(Conversation.session_id == session_id)
    return list((await session.scalars(stmt)).all())


async def get_messages(session: AsyncSession, convo_id: str) -> list[Message]:
    stmt = select(Message).where(Message.conversation_id == convo_id).order_by(Message.sequence)
    return list((await session.scalars(stmt)).all())


async def next_sequence(session: AsyncSession, convo_id: str) -> int:
    stmt = select(func.coalesce(func.max(Message.sequence), -1)).where(
        Message.conversation_id == convo_id
    )
    return int((await session.scalar(stmt)) or -1) + 1


async def add_message(
    session: AsyncSession,
    *,
    convo_id: str,
    role: str,
    content: str,
    token_count: int = 0,
) -> Message:
    seq = await next_sequence(session, convo_id)
    msg = Message(
        id=_uuid(),
        conversation_id=convo_id,
        role=role,
        content=content,
        token_count=token_count,
        sequence=seq,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)
    return msg


async def set_status(session: AsyncSession, convo_id: str, status: str) -> None:
    convo = await session.get(Conversation, convo_id)
    if convo:
        convo.status = status
        await session.commit()
