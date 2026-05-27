"""Alembic environment.

Runs migrations with a *synchronous* psycopg3 engine (same driver, sync mode) to
keep migrations simple, while the app uses the async engine. The URL and target
metadata both come from the application so there is one source of truth.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from beacon.db import models  # noqa: F401 — register tables on Base.metadata
from beacon.db.base import Base
from beacon.settings import settings

config = context.config
target_metadata = Base.metadata

# async URL -> sync URL for migrations (psycopg3 supports both)
SYNC_URL = settings.database_url.replace("+asyncpg", "+psycopg")


def run_migrations_offline() -> None:
    context.configure(url=SYNC_URL, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(SYNC_URL, future=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
