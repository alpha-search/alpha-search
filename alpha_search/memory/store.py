"""Local-first structured memory store using DuckDB (with SQLite fallback).

The ``MemoryStore`` is the core of the Alpha Search persistent memory layer.
It uses DuckDB when available, falling back transparently to SQLite so the
system works on any machine without extra native dependencies.

All public methods are fully typed and documented.  SQL queries use
parameterised placeholders (``?``) to prevent injection.  JSON fields are
serialised with :pyfunc:`json.dumps` and deserialised with
:pyfunc:`json.loads`.

No API keys, tokens, broker credentials, or personally identifiable
information are ever stored \u2014 only research metadata, decisions, and
summaries.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, List, Optional

from alpha_search.memory.models import (
    HandoffRecord,
    MemoryRecord,
    RiskDecision,
    StrategyMemory,
)


class MemoryStore:
    """Local-first structured memory store using DuckDB (with SQLite fallback).

    Example::

        store = MemoryStore(":memory:")
        store.initialize()
        record = MemoryRecord(
            agent_name="researcher",
            memory_type="architecture_decision",
            title="Chose momentum strategy",
            content="Rationale here...",
            tags=["momentum", "aapl"],
        )
        store.add_memory(record)
        recent = store.list_recent(limit=10)
        store.close()
    """

    # ------------------------------------------------------------------ #
    # Construction / connection
    # ------------------------------------------------------------------ #

    def __init__(self, db_path: str = "memory/alpha_search_memory.duckdb") -> None:
        """Initialize the memory store.

        Args:
            db_path: Path to the database file.  The parent
                directory is created automatically if it does not exist.
                Use ``":memory:"`` for an in-memory SQLite store (testing).
        """
        self.db_path: str = db_path
        self.conn: Any = self._connect()
        self.using_duckdb: bool = "duckdb" in self.conn.__class__.__module__

    def _connect(self) -> Any:
        """Connect to DuckDB or fall back to SQLite.

        Returns:
            A database connection object (duckdb.Connection or
            sqlite3.Connection).
        """
        if self.db_path == ":memory:":
            conn = sqlite3.connect(":memory:", check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            return conn
        try:
            import duckdb

            # Detect mock/placeholder modules (real duckdb has __spec__ as ModuleSpec)
            if getattr(duckdb, "__spec__", None) is None and not hasattr(duckdb, "__file__"):
                raise ImportError("duckdb module is a placeholder")
            return duckdb.connect(self.db_path)
        except (ImportError, OSError, AttributeError):
            db_sqlite = self.db_path.replace(".duckdb", ".sqlite")
            conn = sqlite3.connect(db_sqlite, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            return conn

    # ------------------------------------------------------------------ #
    # Schema initialisation
    # ------------------------------------------------------------------ #

    def initialize(self) -> None:
        """Create all tables and indexes.

        Reads *schema.sql* from the same directory as this module and
        executes every statement.  Works transparently with both DuckDB
        and SQLite.
        """
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(schema_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()

        # Accumulate statements, skipping comment-only lines
        statements: List[str] = []
        current: List[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            current.append(line)
            if stripped.endswith(";"):
                statements.append("".join(current).strip())
                current = []
        if current:
            statements.append("".join(current).strip())

        for stmt in statements:
            if not stmt:
                continue
            try:
                self.conn.execute(stmt)
            except Exception:
                # Skip unsupported statements (e.g. COMMENT ON in SQLite)
                pass

    # ------------------------------------------------------------------ #
    # Helper: current timestamp
    # ------------------------------------------------------------------ #

    @staticmethod
    def _now() -> str:
        """Return ISO-8601 UTC timestamp string."""
        return datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------ #
    # Agent memory  CRUD
    # ------------------------------------------------------------------ #

    def add_memory(self, record: MemoryRecord) -> str:
        """Insert a :class:`MemoryRecord` into the *agent_memory* table.

        Args:
            record: The memory record to persist.

        Returns:
            The record's ``id``.
        """
        _ = record.to_row()  # noqa: F841  # noqa: F841
        self.conn.execute(
            """
            INSERT INTO agent_memory
                (id, agent_name, memory_type, title, content, tags,
                 importance_score, status, source_file, related_task,
                 created_at, updated_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.agent_name,
                record.memory_type,
                record.title,
                record.content,
                json.dumps(record.tags),
                record.importance_score,
                record.status,
                record.source_file,
                record.related_task,
                record.created_at.isoformat(),
                record.updated_at.isoformat(),
            ),
        )
        self.conn.commit()
        return record.id

    def get_memory(self, memory_id: str) -> Optional[MemoryRecord]:
        """Retrieve a single :class:`MemoryRecord` by its ``id``.

        Args:
            memory_id: The primary key of the memory.

        Returns:
            The memory record, or ``None`` if not found.
        """
        cursor = self.conn.execute(
            "SELECT * FROM agent_memory WHERE id = ?",
            (memory_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return MemoryRecord.from_row(row)

    def list_recent(self, limit: int = 20) -> List[MemoryRecord]:
        """Return the most recent memory records.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of :class:`MemoryRecord` objects ordered by
            ``created_at`` descending.
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM agent_memory
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [MemoryRecord.from_row(r) for r in rows]

    def search_by_agent(self, agent_name: str, limit: int = 50) -> List[MemoryRecord]:
        """Filter memory records by agent name.

        Args:
            agent_name: Exact agent name to match.
            limit: Maximum number of records to return.

        Returns:
            Matching records ordered by ``created_at`` descending.
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM agent_memory
            WHERE agent_name = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (agent_name, limit),
        )
        rows = cursor.fetchall()
        return [MemoryRecord.from_row(r) for r in rows]

    def search_by_type(self, memory_type: str, limit: int = 50) -> List[MemoryRecord]:
        """Filter memory records by memory type.

        Args:
            memory_type: Exact type string to match (e.g. ``"blocker"``).
            limit: Maximum number of records to return.

        Returns:
            Matching records ordered by ``created_at`` descending.
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM agent_memory
            WHERE memory_type = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (memory_type, limit),
        )
        rows = cursor.fetchall()
        return [MemoryRecord.from_row(r) for r in rows]

    def search_by_tags(self, tags: List[str], limit: int = 50) -> List[MemoryRecord]:
        """Search memory records that contain **any** of the given tags.

        Args:
            tags: List of tag strings to search for.
            limit: Maximum number of records to return.

        Returns:
            Matching records ordered by ``created_at`` descending.
        """
        if not tags:
            return self.list_recent(limit=limit)

        placeholders = " OR ".join("tags LIKE ?" for _ in tags)
        like_params = [f'%"{tag}"%' for tag in tags]
        cursor = self.conn.execute(
            f"""
            SELECT * FROM agent_memory
            WHERE {placeholders}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*like_params, limit),
        )
        rows = cursor.fetchall()
        return [MemoryRecord.from_row(r) for r in rows]

    def update_memory(self, memory_id: str, **updates: Any) -> bool:
        """Partially update an *agent_memory* record.

        Automatically sets ``updated_at`` to the current UTC time.

        Args:
            memory_id: The primary key of the record to update.
            **updates: Column-name to new-value mappings.  Supported keys:
                ``agent_name``, ``memory_type``, ``content``, ``tags``,
                ``status``.

        Returns:
            ``True`` if at least one row was updated.
        """
        allowed = {"agent_name", "memory_type", "title", "content", "tags", "status"}
        columns = []
        params: List[Any] = []

        for key, value in updates.items():
            if key not in allowed:
                continue
            if key == "tags" and isinstance(value, list):
                value = json.dumps(value)
            columns.append(f"{key} = ?")
            params.append(value)

        if not columns:
            return False

        columns.append("updated_at = ?")
        params.append(self._now())
        params.append(memory_id)

        sql = f"""
            UPDATE agent_memory
            SET {', '.join(columns)}
            WHERE id = ?
        """
        self.conn.execute(sql, params)
        self.conn.commit()
        return True

    def resolve_memory(self, memory_id: str) -> bool:
        """Set the status of a memory record to ``"resolved"``.

        Args:
            memory_id: The primary key of the record.

        Returns:
            ``True`` if the record was found and updated.
        """
        return self.update_memory(memory_id, status="resolved")

    # ------------------------------------------------------------------ #
    # Flexible query used by retrieval layer
    # ------------------------------------------------------------------ #

    def get_memories(
        self,
        agent_name: Optional[str] = None,
        memory_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryRecord]:
        """Flexible query for memory records with optional filters.

        Args:
            agent_name: Filter by agent name.
            memory_type: Filter by memory type.
            status: Filter by status.
            limit: Maximum number of records.

        Returns:
            Matching MemoryRecord objects.
        """
        conditions: List[str] = []
        params: List[Any] = []

        if agent_name is not None:
            conditions.append("agent_name = ?")
            params.append(agent_name)
        if memory_type is not None:
            conditions.append("memory_type = ?")
            params.append(memory_type)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT * FROM agent_memory
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        return [MemoryRecord.from_row(r) for r in rows]

    def get_recent_decisions(self, limit: int = 10) -> List[MemoryRecord]:
        """Return recent architecture decisions.

        Args:
            limit: Maximum number of records.

        Returns:
            MemoryRecord objects with memory_type='architecture_decision'.
        """
        return self.get_memories(
            memory_type="architecture_decision",
            limit=limit,
        )

    def get_unresolved_blockers(self, limit: int = 10) -> List[MemoryRecord]:
        """Return unresolved blocker records.

        Args:
            limit: Maximum number of records.

        Returns:
            MemoryRecord objects with memory_type='blocker' and status='active'.
        """
        return self.get_memories(
            memory_type="blocker",
            status="active",
            limit=limit,
        )

    # ------------------------------------------------------------------ #
    # Strategy memory  CRUD
    # ------------------------------------------------------------------ #

    def add_strategy_memory(self, record: StrategyMemory) -> str:
        """Insert a :class:`StrategyMemory` into the *strategy_memory* table.

        Args:
            record: The strategy memory to persist.

        Returns:
            The record's ``id``.
        """
        self.conn.execute(
            """
            INSERT INTO strategy_memory
                (id, strategy_name, strategy_type, market, asset_class,
                 universe, hypothesis, result_summary, sharpe,
                 max_drawdown, total_return, win_rate, turnover,
                 transaction_cost_assumption, validation_method, verdict,
                 rejection_reason, lessons_learned, created_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.strategy_name,
                record.strategy_type,
                record.market,
                record.asset_class,
                json.dumps(record.universe),
                record.hypothesis,
                record.result_summary,
                record.sharpe,
                record.max_drawdown,
                record.total_return,
                record.win_rate,
                record.turnover,
                record.transaction_cost_assumption,
                record.validation_method,
                record.verdict,
                record.rejection_reason,
                record.lessons_learned,
                record.created_at.isoformat(),
            ),
        )
        self.conn.commit()
        return record.id

    def get_strategy_memory(self, strategy_id: str) -> Optional[StrategyMemory]:
        """Retrieve a single :class:`StrategyMemory` by its ``id``.

        Args:
            strategy_id: The primary key of the strategy record.

        Returns:
            The strategy memory, or ``None`` if not found.
        """
        cursor = self.conn.execute(
            "SELECT * FROM strategy_memory WHERE id = ?",
            (strategy_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return StrategyMemory.from_row(row)

    def list_strategy_results(
        self, strategy_type: Optional[str] = None, limit: int = 50
    ) -> List[StrategyMemory]:
        """List strategy memory records.

        Args:
            strategy_type: If provided, filter to this strategy type.
            limit: Maximum number of records to return.

        Returns:
            List of :class:`StrategyMemory` objects ordered by
            ``created_at`` descending.
        """
        if strategy_type:
            cursor = self.conn.execute(
                """
                SELECT * FROM strategy_memory
                WHERE strategy_type = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (strategy_type, limit),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM strategy_memory
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = cursor.fetchall()
        return [StrategyMemory.from_row(r) for r in rows]

    def get_strategy_memories(
        self,
        strategy_type: Optional[str] = None,
        verdict: Optional[str] = None,
        limit: int = 50,
    ) -> List[StrategyMemory]:
        """Flexible query for strategy memories.

        Args:
            strategy_type: Filter by strategy type.
            verdict: Filter by verdict.
            limit: Maximum number of records.

        Returns:
            Matching StrategyMemory objects.
        """
        conditions: List[str] = []
        params: List[Any] = []

        if strategy_type is not None:
            conditions.append("strategy_type = ?")
            params.append(strategy_type)
        if verdict is not None:
            conditions.append("verdict = ?")
            params.append(verdict)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"""
            SELECT * FROM strategy_memory
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """
        params.append(limit)
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        return [StrategyMemory.from_row(r) for r in rows]

    def list_rejected_strategies(self, limit: int = 50) -> List[StrategyMemory]:
        """List strategy records whose ``verdict`` is ``"rejected"``.

        Args:
            limit: Maximum number of records to return.

        Returns:
            Rejected strategy records ordered by ``created_at`` descending.
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM strategy_memory
            WHERE verdict = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            ("rejected", limit),
        )
        rows = cursor.fetchall()
        return [StrategyMemory.from_row(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Handoff  CRUD
    # ------------------------------------------------------------------ #

    def add_handoff(self, record: HandoffRecord) -> str:
        """Insert a :class:`HandoffRecord` into the *handoffs* table.

        Args:
            record: The handoff record to persist.

        Returns:
            The record's ``id``.
        """
        self.conn.execute(
            """
            INSERT INTO handoffs
                (id, from_agent, to_agent, task, context, status, created_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.from_agent,
                record.to_agent,
                record.task,
                record.context,
                record.status,
                record.created_at.isoformat(),
            ),
        )
        self.conn.commit()
        return record.id

    def get_handoff(self, handoff_id: str) -> Optional[HandoffRecord]:
        """Retrieve a single :class:`HandoffRecord` by its ``id``.

        Args:
            handoff_id: The primary key of the handoff record.

        Returns:
            The handoff record, or ``None`` if not found.
        """
        cursor = self.conn.execute(
            "SELECT * FROM handoffs WHERE id = ?",
            (handoff_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return HandoffRecord.from_row(row)

    def list_recent_handoffs(self, limit: int = 50) -> List[HandoffRecord]:
        """Return the most recent handoff records.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of :class:`HandoffRecord` objects ordered by
            ``created_at`` descending.
        """
        cursor = self.conn.execute(
            """
            SELECT * FROM handoffs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [HandoffRecord.from_row(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Risk decision  CRUD
    # ------------------------------------------------------------------ #

    def add_risk_decision(self, record: RiskDecision) -> str:
        """Insert a :class:`RiskDecision` into the *risk_decisions* table.

        Args:
            record: The risk decision to persist.

        Returns:
            The record's ``id``.
        """
        self.conn.execute(
            """
            INSERT INTO risk_decisions
                (id, agent_name, object_type, object_id,
                 decision, reason, severity, created_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.agent_name,
                record.object_type,
                record.object_id,
                record.decision,
                record.reason,
                record.severity,
                record.created_at.isoformat(),
            ),
        )
        self.conn.commit()
        return record.id

    def get_risk_decision(self, decision_id: str) -> Optional[RiskDecision]:
        """Retrieve a single :class:`RiskDecision` by its ``id``.

        Args:
            decision_id: The primary key of the risk decision.

        Returns:
            The risk decision, or ``None`` if not found.
        """
        cursor = self.conn.execute(
            "SELECT * FROM risk_decisions WHERE id = ?",
            (decision_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return RiskDecision.from_row(row)

    def list_risk_decisions(
        self, severity: Optional[str] = None, limit: int = 50
    ) -> List[RiskDecision]:
        """List risk decision records.

        Args:
            severity: If provided, filter to this severity level
                (``"low"``, ``"medium"``, ``"high"``, ``"critical"``).
            limit: Maximum number of records to return.

        Returns:
            List of :class:`RiskDecision` objects ordered by
            ``created_at`` descending.
        """
        if severity:
            cursor = self.conn.execute(
                """
                SELECT * FROM risk_decisions
                WHERE severity = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (severity, limit),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT * FROM risk_decisions
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
        rows = cursor.fetchall()
        return [RiskDecision.from_row(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def close(self) -> None:
        """Close the database connection.

        Safe to call multiple times \u2014 subsequent calls are no-ops.
        """
        try:
            self.conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # Context-manager support
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "MemoryStore":
        """Enter runtime context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit runtime context, closing the connection."""
        self.close()

    # ------------------------------------------------------------------ #
    # Debug / diagnostics
    # ------------------------------------------------------------------ #

    def stats(self) -> dict:
        """Return row counts for all four tables.

        Returns:
            Dict mapping table name to integer row count.
        """
        tables = [
            "agent_memory",
            "strategy_memory",
            "handoffs",
            "risk_decisions",
        ]
        result: dict = {}
        for table in tables:
            try:
                cursor = self.conn.execute(
                    f"SELECT COUNT(*) FROM {table}"
                )
                result[table] = cursor.fetchone()[0]
            except Exception:
                result[table] = 0
        return result

    def __repr__(self) -> str:
        backend = "duckdb" if self.using_duckdb else "sqlite"
        return f"<{self.__class__.__name__} backend={backend} path={self.db_path!r}>"
