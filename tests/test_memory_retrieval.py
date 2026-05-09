"""Comprehensive tests for MemoryRetriever context building.

Seeds the store with structured data, then verifies that each retrieval
method produces well-formatted, non-empty context strings.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from alpha_search.memory import (
    AgentJournal,
    MemoryRecord,
    MemoryRetriever,
    MemoryStore,
    StrategyMemory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_retriever():
    """Provide a MemoryRetriever + AgentJournal seeded with test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_memory.duckdb")
        store = MemoryStore(db_path=db_path)
        store.initialize()
        journal = AgentJournal(store=store, journal_dir=os.path.join(tmpdir, "memory"))
        retriever = MemoryRetriever(store=store)

        # --- seed data ---
        # 3 decisions for architect
        journal.log_decision(
            agent_name="architect",
            decision="Use SQLite as default store",
            rationale="Zero external deps, WAL mode, good enough.",
            importance_score=0.9,
        )
        journal.log_decision(
            agent_name="architect",
            decision="Pydantic v2 for all models",
            rationale="Faster validation, better JSON schema.",
            importance_score=0.8,
        )
        journal.log_decision(
            agent_name="architect",
            decision="Markdown journals for humans",
            rationale="Dual-write gives us both structured DB and readable logs.",
            importance_score=0.7,
        )

        # 1 decision for another agent
        journal.log_decision(
            agent_name="executor",
            decision="Use asyncio for data fetch",
            rationale="Concurrent downloads speed up backfill by 5x.",
            importance_score=0.6,
        )

        # 2 blockers: 1 active, 1 resolved
        blocker_active = MemoryRecord(
            agent_name="executor",
            memory_type="blocker",
            title="DuckDB missing in CI",
            content="CI environment only has SQLite; need fallback logic.",
            status="active",
            tags=["ci", "infrastructure"],
        )
        store.add_memory(blocker_active)

        blocker_resolved = MemoryRecord(
            agent_name="reviewer",
            memory_type="blocker",
            title="Test coverage below 90%",
            content="Added 15 new tests to reach 95% coverage.",
            status="resolved",
            tags=["testing"],
        )
        store.add_memory(blocker_resolved)

        # Strategies: accepted + rejected
        journal.log_strategy_result(
            StrategyMemory(
                strategy_name="Momentum ETF",
                strategy_type="momentum",
                universe=["SPY", "QQQ"],
                hypothesis="Trend following on broad ETFs.",
                sharpe=1.5,
                max_drawdown=-0.08,
                verdict="accepted",
                lessons_learned="Clean signals and low turnover.",
            )
        )
        journal.log_strategy_result(
            StrategyMemory(
                strategy_name="Crypto Arbitrage",
                strategy_type="momentum",
                universe=["BTC", "ETH"],
                hypothesis="Cross-exchange price gaps.",
                sharpe=0.5,
                max_drawdown=-0.25,
                verdict="rejected",
                rejection_reason="Execution slippage exceeds expected edge.",
            )
        )
        journal.log_strategy_result(
            StrategyMemory(
                strategy_name="Mean Reversion",
                strategy_type="mean_reversion",
                universe=["AAPL", "MSFT"],
                hypothesis="Large-cap mean reversion after earnings.",
                sharpe=1.2,
                max_drawdown=-0.10,
                verdict="accepted",
                lessons_learned="Strong mean-reversion in large-cap tech.",
            )
        )

        yield retriever, journal, store
        store.close()


# ---------------------------------------------------------------------------
# 1. get_agent_context
# ---------------------------------------------------------------------------


def test_get_agent_context(temp_retriever):
    """Seeded 3 decisions for architect; context contains decision titles."""
    retriever, _journal, _store = temp_retriever

    ctx = retriever.get_agent_context("architect")
    assert isinstance(ctx, str)
    assert len(ctx) > 0  # non-empty
    assert "architect" in ctx.lower()
    # Should contain decision references
    assert "Use SQLite" in ctx or "Pydantic" in ctx or "Markdown" in ctx

    # Executor should have its decision
    ctx_exec = retriever.get_agent_context("executor")
    assert "asyncio" in ctx_exec or "executor" in ctx_exec.lower()

    # Nonexistent agent returns a string (with "No recent" or similar)
    ctx_none = retriever.get_agent_context("nonexistent")
    assert isinstance(ctx_none, str)


# ---------------------------------------------------------------------------
# 2. get_project_context
# ---------------------------------------------------------------------------


def test_get_project_context(temp_retriever):
    """Project context contains the header and decision data."""
    retriever, _journal, _store = temp_retriever

    ctx = retriever.get_project_context()
    assert isinstance(ctx, str)
    assert len(ctx) > 0  # non-empty
    assert "Project memory" in ctx
    # Should contain decision content
    assert "Use SQLite" in ctx or "Pydantic" in ctx


# ---------------------------------------------------------------------------
# 3. get_strategy_lessons
# ---------------------------------------------------------------------------


def test_get_strategy_lessons(temp_retriever):
    """Strategy lessons for 'momentum' returns only momentum-type strategies."""
    retriever, _journal, _store = temp_retriever

    ctx_momentum = retriever.get_strategy_lessons("momentum")
    assert isinstance(ctx_momentum, str)
    assert len(ctx_momentum) > 0
    assert "Momentum ETF" in ctx_momentum or "Crypto Arbitrage" in ctx_momentum
    # Should NOT include mean_reversion strategy
    assert "Mean Reversion" not in ctx_momentum

    # All strategies when using a different type
    ctx_mr = retriever.get_strategy_lessons("mean_reversion")
    assert "Mean Reversion" in ctx_mr
    assert "Momentum ETF" not in ctx_mr

    # Both accepted and rejected sections should be present
    assert "Accepted" in ctx_momentum
    assert "Rejected" in ctx_momentum


# ---------------------------------------------------------------------------
# 4. get_unresolved_blockers
# ---------------------------------------------------------------------------


def test_get_unresolved_blockers(temp_retriever):
    """Only the active blocker is referenced; resolved is excluded."""
    retriever, _journal, _store = temp_retriever

    ctx = retriever.get_unresolved_blockers()
    assert isinstance(ctx, str)
    assert len(ctx) > 0
    assert "DuckDB missing in CI" in ctx or "blockers" in ctx.lower()
    # Resolved blocker should NOT appear
    assert "Test coverage below 90%" not in ctx


# ---------------------------------------------------------------------------
# 5. get_recent_decisions
# ---------------------------------------------------------------------------


def test_get_recent_decisions(temp_retriever):
    """get_recent_decisions returns recent architecture decisions."""
    retriever, _journal, _store = temp_retriever

    ctx = retriever.get_recent_decisions(3)
    assert isinstance(ctx, str)
    assert len(ctx) > 0
    assert "Recent decisions" in ctx
    # Should contain at least one decision title
    assert "Use SQLite" in ctx or "Pydantic" in ctx or "Markdown" in ctx


# ---------------------------------------------------------------------------
# 6. build_agent_prompt_context
# ---------------------------------------------------------------------------


def test_build_agent_prompt_context(temp_retriever):
    """Comprehensive context contains multiple sections."""
    retriever, _journal, _store = temp_retriever

    ctx = retriever.build_agent_prompt_context("architect")
    assert isinstance(ctx, str)
    assert len(ctx) > 0  # non-empty

    # Should contain project context
    assert "Project memory" in ctx

    # Should contain agent-specific context
    assert "architect" in ctx.lower()

    # Should contain blockers section
    assert "blockers" in ctx.lower() or "Blockers" in ctx

    # Should contain decisions section
    assert "decisions" in ctx.lower() or "Decisions" in ctx

    # Should contain strategy lessons
    assert "Strategy" in ctx or "strategy" in ctx

    # Verify it's a multi-section string (contains multiple headers)
    header_count = sum(1 for line in ctx.splitlines() if line.startswith("=") or line.startswith("-"))
    assert header_count >= 1 or len(ctx.splitlines()) > 10

    # Should have start/end markers
    assert "Alpha Search Agent Context" in ctx
    assert "End Context" in ctx
