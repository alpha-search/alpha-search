"""Comprehensive tests for AgentJournal dual-write (DB + Markdown).

Every test verifies both the database side and the Markdown file side of
the journal write.  All I/O is confined to temporary directories.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from alpha_search.memory import (
    AgentJournal,
    MemoryStore,
    StrategyMemory,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_journal():
    """Provide an AgentJournal backed by temp DB + temp journal directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_memory.duckdb")
        journal_dir = os.path.join(tmpdir, "memory")
        store = MemoryStore(db_path=db_path)
        store.initialize()
        journal = AgentJournal(store=store, journal_dir=journal_dir)
        yield journal, journal_dir
        store.close()


# ---------------------------------------------------------------------------
# 1. log_task writes both DB and Markdown
# ---------------------------------------------------------------------------


def test_log_task_writes_db(temp_journal):
    """log_task() persists to DB and creates a Markdown entry."""
    journal, journal_dir = temp_journal

    journal.log_task(
        agent_name="architect",
        task="Design schema",
        status="completed",
        notes="Created the agent_memory table with all required columns.",
        tags=["database", "schema"],
    )

    # -- DB side --
    db_results = journal.store.search_by_agent("architect")
    assert len(db_results) == 1
    db_entry = db_results[0]
    assert db_entry.title == "Design schema"
    assert db_entry.memory_type == "agent_task"
    assert db_entry.tags == ["database", "schema"]
    assert db_entry.status == "completed"

    # -- Markdown side --
    md_path = os.path.join(journal_dir, "agent_journal.md")
    assert os.path.exists(md_path)
    md_content = open(md_path, "r", encoding="utf-8").read()
    assert "Design schema" in md_content
    assert "architect" in md_content
    assert "agent_memory" in md_content
    assert "### " in md_content  # heading
    assert "---" in md_content  # separator


# ---------------------------------------------------------------------------
# 2. log_decision writes both DB and Markdown
# ---------------------------------------------------------------------------


def test_log_decision_writes_both(temp_journal):
    """log_decision() persists to DB and writes architecture_decisions.md."""
    journal, journal_dir = temp_journal

    journal.log_decision(
        agent_name="architect",
        decision="Use SQLite for memory store",
        rationale="SQLite requires no external deps and supports WAL mode.",
        importance_score=0.9,
    )

    # -- DB side --
    db_results = journal.store.search_by_agent("architect")
    assert len(db_results) == 1
    assert db_results[0].memory_type == "architecture_decision"
    assert db_results[0].title == "Use SQLite for memory store"
    assert db_results[0].importance_score == 0.9

    # -- Markdown side --
    md_path = os.path.join(journal_dir, "architecture_decisions.md")
    assert os.path.exists(md_path)
    md_content = open(md_path, "r", encoding="utf-8").read()
    assert "Use SQLite for memory store" in md_content
    assert "0.9" in md_content
    assert "architecture_decisions" in md_path


# ---------------------------------------------------------------------------
# 3. log_blocker writes both DB and Markdown with severity
# ---------------------------------------------------------------------------


def test_log_blocker(temp_journal):
    """log_blocker() persists severity to DB and shows it in Markdown."""
    journal, journal_dir = temp_journal

    journal.log_blocker(
        agent_name="executor",
        blocker="DuckDB not available in CI",
        severity="high",
        tags=["ci", "infrastructure"],
    )

    # -- DB side --
    db_results = journal.store.search_by_type("blocker")
    assert len(db_results) == 1
    assert db_results[0].title == "DuckDB not available in CI"
    assert db_results[0].memory_type == "blocker"
    assert "ci" in db_results[0].tags

    # -- Markdown side --
    md_path = os.path.join(journal_dir, "agent_journal.md")
    assert os.path.exists(md_path)
    md_content = open(md_path, "r", encoding="utf-8").read()
    assert "DuckDB not available in CI" in md_content
    assert "high" in md_content


# ---------------------------------------------------------------------------
# 4. log_handoff writes both DB and Markdown
# ---------------------------------------------------------------------------


def test_log_handoff(temp_journal):
    """log_handoff() persists to handoffs table and agent_journal.md."""
    journal, journal_dir = temp_journal

    journal.log_handoff(
        from_agent="architect",
        to_agent="executor",
        task="Implement the backtest engine",
        context="Use vectorized operations for performance.",
    )

    # -- DB side (handoffs table) --
    handoffs = journal.store.list_recent_handoffs()
    assert len(handoffs) == 1
    assert handoffs[0].from_agent == "architect"
    assert handoffs[0].to_agent == "executor"
    assert handoffs[0].task == "Implement the backtest engine"
    assert handoffs[0].context == "Use vectorized operations for performance."
    assert handoffs[0].status == "pending"

    # -- Markdown side --
    md_path = os.path.join(journal_dir, "agent_journal.md")
    assert os.path.exists(md_path)
    md_content = open(md_path, "r", encoding="utf-8").read()
    assert "Handoff: architect" in md_content or "architect" in md_content
    assert "backtest engine" in md_content


# ---------------------------------------------------------------------------
# 5. log_strategy_result writes both DB and Markdown
# ---------------------------------------------------------------------------


def test_log_strategy_result(temp_journal):
    """log_strategy_result() persists to strategy_memory and strategy_findings.md."""
    journal, journal_dir = temp_journal

    strategy = StrategyMemory(
        strategy_name="Pairs Trading",
        strategy_type="mean_reversion",
        universe=["EWA", "EWC"],
        hypothesis="Cointegrated pairs revert to mean.",
        sharpe=0.5,
        max_drawdown=-0.25,
        verdict="rejected",
        rejection_reason="Cointegration broke down during market stress.",
    )

    journal.log_strategy_result(strategy)

    # -- DB side --
    results = journal.store.list_strategy_results()
    assert len(results) == 1
    assert results[0].strategy_name == "Pairs Trading"
    assert results[0].verdict == "rejected"
    assert results[0].universe == ["EWA", "EWC"]

    # -- Markdown side --
    md_path = os.path.join(journal_dir, "strategy_findings.md")
    assert os.path.exists(md_path)
    md_content = open(md_path, "r", encoding="utf-8").read()
    assert "Pairs Trading" in md_content
    assert "mean_reversion" in md_content
    assert "EWA" in md_content
    assert "Cointegration broke" in md_content or "rejected" in md_content


# ---------------------------------------------------------------------------
# 6. log_risk_decision writes both DB and Markdown
# ---------------------------------------------------------------------------


def test_log_risk_decision(temp_journal):
    """log_risk_decision() persists to risk_decisions table and risk_log.md."""
    journal, journal_dir = temp_journal

    journal.log_risk_decision(
        agent_name="risk_manager",
        object_type="strategy",
        object_id="aapl_momentum_001",
        decision="rejected",
        reason="AAPL position hit stop-loss at 170.",
        severity="critical",
    )

    # -- DB side --
    decisions = journal.store.list_risk_decisions()
    assert len(decisions) == 1
    assert decisions[0].agent_name == "risk_manager"
    assert decisions[0].object_type == "strategy"
    assert decisions[0].object_id == "aapl_momentum_001"
    assert decisions[0].decision == "rejected"
    assert decisions[0].severity == "critical"

    # -- Markdown side --
    md_path = os.path.join(journal_dir, "risk_log.md")
    assert os.path.exists(md_path)
    md_content = open(md_path, "r", encoding="utf-8").read()
    assert "critical" in md_content or "CRITICAL" in md_content or "🔴" in md_content
    assert "AAPL position hit stop-loss" in md_content


# ---------------------------------------------------------------------------
# 7. Multiple entries accumulate correctly
# ---------------------------------------------------------------------------


def test_multiple_entries(temp_journal):
    """Log 5 tasks; all appear in DB and Markdown."""
    journal, journal_dir = temp_journal

    for i in range(5):
        journal.log_task(
            agent_name="executor",
            task=f"Task {i}",
            status="completed",
            notes=f"Completed step {i} of the pipeline.",
            tags=["pipeline"],
        )

    # -- DB side --
    db_results = journal.store.search_by_agent("executor")
    assert len(db_results) == 5
    titles = {r.title for r in db_results}
    assert titles == {"Task 0", "Task 1", "Task 2", "Task 3", "Task 4"}

    # -- Markdown side --
    md_path = os.path.join(journal_dir, "agent_journal.md")
    md_content = open(md_path, "r", encoding="utf-8").read()
    for i in range(5):
        assert f"Task {i}" in md_content
        assert f"step {i}" in md_content


# ---------------------------------------------------------------------------
# 8. Markdown formatting quality
# ---------------------------------------------------------------------------


def test_markdown_formatting(temp_journal):
    """Logged Markdown contains proper headings, timestamps, and separators."""
    journal, journal_dir = temp_journal

    journal.log_decision(
        agent_name="architect",
        decision="Use Pydantic v2 for models",
        rationale="Pydantic v2 offers better performance and strict validation.",
        importance_score=0.85,
    )

    md_path = os.path.join(journal_dir, "architecture_decisions.md")
    md_content = open(md_path, "r", encoding="utf-8").read()

    # Headings
    assert "### " in md_content
    # Decision label
    assert "**Decision:**" in md_content
    assert "Use Pydantic v2 for models" in md_content
    # Rationale
    assert "**Rationale:**" in md_content
    assert "Pydantic v2 offers better performance" in md_content
    # Importance
    assert "**Importance:**" in md_content
    assert "0.85" in md_content or "0.9" in md_content
    # Separator
    assert "---" in md_content
