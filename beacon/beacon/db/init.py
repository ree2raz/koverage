"""Dev convenience: create tables without Alembic.

    python -m beacon.db.init

Alembic (alembic upgrade head) is the canonical path; this exists so a fresh
clone can come up in one step during the demo.
"""

from __future__ import annotations

import asyncio

from .base import Base, engine
from . import models  # noqa: F401 — register tables on Base.metadata


async def _create() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("beacon: tables created")


if __name__ == "__main__":
    asyncio.run(_create())
