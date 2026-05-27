"""initial schema: conversations, messages, inference_logs

Revision ID: 0001
Revises:
Create Date: 2026-05-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_NOW = sa.text("now()")
_EMPTY_JSON = sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("title", sa.String(200), nullable=False, server_default="New conversation"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("default_model", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW),
    )
    op.create_index("ix_conversations_session_id", "conversations", ["session_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_convo_seq", "messages", ["conversation_id", "sequence"])

    op.create_table(
        "inference_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("message_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("session_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("error_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ttft_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("input_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("output_preview", sa.Text(), nullable=False, server_default=""),
        sa.Column("redaction_counts", JSONB(), nullable=False, server_default=_EMPTY_JSON),
        sa.Column("meta", JSONB(), nullable=False, server_default=_EMPTY_JSON),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW),
    )
    op.create_index("ix_inference_logs_request_id", "inference_logs", ["request_id"], unique=True)
    op.create_index("ix_inference_logs_conversation_id", "inference_logs", ["conversation_id"])
    op.create_index("ix_inference_logs_provider", "inference_logs", ["provider"])
    op.create_index("ix_inference_logs_model", "inference_logs", ["model"])
    op.create_index("ix_inference_logs_status", "inference_logs", ["status"])
    op.create_index("ix_inference_logs_ts", "inference_logs", ["ts"])
    op.create_index("ix_logs_ts_provider_model", "inference_logs", ["ts", "provider", "model"])


def downgrade() -> None:
    op.drop_table("inference_logs")
    op.drop_table("messages")
    op.drop_table("conversations")
