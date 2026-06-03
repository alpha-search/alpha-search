"""Create all relational tables, then apply the TimescaleDB schema.

Usage: ``python -m scripts.init_db`` (from the backend directory).

For production use Prisma migrations (``prisma migrate deploy``) or Alembic;
this script is a fast path for local development and CI.
"""
from __future__ import annotations

import asyncio
import pathlib

from sqlalchemy import text

from app.db.models import Base
from app.db.session import engine

_TIMESCALE_SQL = pathlib.Path(__file__).resolve().parents[1] / "sql" / "timescale.sql"


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("✓ relational tables created")

        if _TIMESCALE_SQL.exists():
            try:
                await conn.execute(text(_TIMESCALE_SQL.read_text()))
                print("✓ TimescaleDB hypertable + policies applied")
            except Exception as exc:  # TimescaleDB extension may be absent locally
                print(f"⚠ skipped TimescaleDB setup ({exc.__class__.__name__}): {exc}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
