"""Create all relational tables, then (best-effort) apply the TimescaleDB schema.

Usage: ``python -m scripts.init_db`` (from the backend directory).

Design notes:

* Table creation runs in its **own** committed transaction so it is never rolled
  back by a later TimescaleDB step (e.g. when running against plain PostgreSQL
  without the extension, as the no-Docker local runner does).
* The TimescaleDB file is applied statement-by-statement in AUTOCOMMIT mode,
  because asyncpg cannot run a multi-statement blob as a single prepared
  statement. Each statement is independent and best-effort, so a missing
  extension degrades gracefully instead of aborting setup.

For production use Prisma migrations (``prisma migrate deploy``) or Alembic;
this script is a fast path for local development and CI.
"""
from __future__ import annotations

import asyncio
import pathlib
import re

from sqlalchemy import text

from app.db.models import Base
from app.db.session import engine

_TIMESCALE_SQL = pathlib.Path(__file__).resolve().parents[1] / "sql" / "timescale.sql"


def _split_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements, stripping line comments.

    The TimescaleDB schema contains no dollar-quoted function bodies, so a simple
    semicolon split (after removing ``-- ...`` comments) is correct here.
    """
    without_comments = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in without_comments.split(";") if s.strip()]


async def main() -> None:
    # 1) Relational tables — committed independently.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ relational tables created")

    # 2) TimescaleDB hypertable + policies — best-effort, statement by statement.
    if _TIMESCALE_SQL.exists():
        statements = _split_statements(_TIMESCALE_SQL.read_text())
        applied = 0
        async with engine.connect() as conn:
            autocommit = await conn.execution_options(isolation_level="AUTOCOMMIT")
            for stmt in statements:
                try:
                    await autocommit.exec_driver_sql(stmt)
                    applied += 1
                except Exception as exc:  # extension missing, etc.
                    print(f"⚠ skipped TimescaleDB statement ({exc.__class__.__name__})")
        if applied:
            print(f"✓ applied {applied}/{len(statements)} TimescaleDB statements")
        else:
            print("⚠ TimescaleDB not available — skipped (relational tables are ready)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
