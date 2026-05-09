"""Comprehensive tests for MemoryStore CRUD operations.

Uses SQLite via the MemoryStore compatibility layer.
No writes to the real filesystem outside of temp directories.
"""

from __future__ import annotations

import os
import tempfile
import time
from datetime import datetime, timedelta, timezone

import pytest

from alpha_search.memory import (
    HandoffRecord,
    MemoryRecord,
    MemoryStore,
    RiskDecision,
    StrategyMemory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_store():
    """Provide an initialized MemoryStore backed by a temporary SQLite DB."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_memory.duckdb")
        store = MemoryStore(db_path=db_path)
        store.initialize()
        yield store
        store.close()


@pytest.fixture
def sample_memory():
    """Return a sample MemoryRecord for use in tests."""
    return MemoryRecord(
        agent_name="architect",
        memory_type="agent_task",
        title="Design module layout",
        content="Created the memory module with store, journal, and retriever.",
        tags=["architecture", "memory"],
    )


@pytest.fixture
def sample_strategy():
    """Return a sample StrategyMemory for use in tests."""
    return StrategyMemory(
        strategy_name="Momentum Breakout",
        strategy_type="momentum",
        universe=["AAPL", "MSFT", "GOOGL"],
        hypothesis="Price momentum persists over short horizons.",
        result_summary="Strong backtest results across multiple timeframes.",
        sharpe=1.8,
        max_drawdown=-0.12,
        total_return=0.35,
        verdict="accepted",
        lessons_learned="Works best with volume confirmation.",
    )


# ---------------------------------------------------------------------------
# 1. MemoryRecord model tests
# ---------------------------------------------------------------------------


def test_memory_record_creation():
    """Create MemoryRecord with all fields; verify defaults and clamping."""
    now = datetime.now(timezone.utc)
    record = MemoryRecord(
        agent_name="test_agent",
        memory_type="architecture_decision",
        title="Test Task",
        content="This is test content.",
        status="active",
        importance_score=0.75,
        tags=["tag1", "tag2"],
    )

    # All explicit fields preserved
    assert record.agent_name == "test_agent"
    assert record.memory_type == "architecture_decision"
    assert record.title == "Test Task"
    assert record.content == "This is test content."
    assert record.status == "active"
    assert record.importance_score == 0.75
    assert record.tags == ["tag1", "tag2"]

    # Defaults
    assert record.id  # non-empty UUID string
    assert isinstance(record.id, str)
    assert len(record.id) == 36  # UUID4 length
    assert record.created_at is not None
    assert record.updated_at is not None
    assert (record.created_at - now).total_seconds() < 5

    # Alias properties
    assert record.score == 0.75
    assert isinstance(record.meta, dict)


def test_memory_record_defaults():
    """Verify default values when creating a minimal MemoryRecord."""
    record = MemoryRecord(
        agent_name="agent",
        memory_type="agent_task",
        title="Minimal",
    )
    assert record.memory_type == "agent_task"
    assert record.status == "active"
    assert record.importance_score == 0.5
    assert record.tags == []
    assert record.content == ""
    assert record.id
    assert record.created_at is not None


def test_importance_score_clamping():
    """Verify importance_score is clamped to [0, 1]."""
    r1 = MemoryRecord(
        agent_name="a", memory_type="agent_task", title="t", importance_score=1.5
    )
    assert r1.importance_score == 1.0

    r2 = MemoryRecord(
        agent_name="a", memory_type="agent_task", title="t", importance_score=-0.3
    )
    assert r2.importance_score == 0.0

    r3 = MemoryRecord(
        agent_name="a", memory_type="agent_task", title="t", importance_score=2.0
    )
    assert r3.importance_score == 1.0

    r4 = MemoryRecord(
        agent_name="a", memory_type="agent_task", title="t", importance_score=-10.0
    )
    assert r4.importance_score == 0.0


def test_memory_type_validation():
    """Verify memory_type must be one of the allowed values."""
    # Valid types
    for mt in [
        "architecture_decision",
        "agent_task",
        "blocker",
        "handoff",
        "strategy_result",
        "risk_decision",
        "research_finding",
        "data_quality_issue",
        "release_decision",
        "user_preference",
    ]:
        r = MemoryRecord(agent_name="a", memory_type=mt, title="t")
        assert r.memory_type == mt

    # Invalid type
    with pytest.raises(ValueError):
        MemoryRecord(agent_name="a", memory_type="invalid", title="t")


# ---------------------------------------------------------------------------
# 2. StrategyMemory model tests
# ---------------------------------------------------------------------------


def test_strategy_memory_creation(sample_strategy):
    """Create StrategyMemory with all fields; verify values."""
    assert sample_strategy.strategy_name == "Momentum Breakout"
    assert sample_strategy.strategy_type == "momentum"
    assert sample_strategy.universe == ["AAPL", "MSFT", "GOOGL"]
    assert sample_strategy.hypothesis == "Price momentum persists over short horizons."
    assert sample_strategy.sharpe == 1.8
    assert sample_strategy.max_drawdown == -0.12
    assert sample_strategy.verdict == "accepted"
    assert sample_strategy.id
    assert sample_strategy.created_at is not None

    # Alias properties
    assert sample_strategy.name == "Momentum Breakout"
    assert sample_strategy.rationale == "Works best with volume confirmation."
    assert "sharpe" in sample_strategy.metrics


def test_strategy_memory_verdict_validation():
    """Verify verdict validation accepts only allowed values."""
    for v in ["accepted", "rejected", "watch", "needs_more_testing"]:
        s = StrategyMemory(
            strategy_name="S", strategy_type="momentum", hypothesis="h", verdict=v
        )
        assert s.verdict == v

    with pytest.raises(ValueError):
        StrategyMemory(
            strategy_name="S", strategy_type="momentum", hypothesis="h", verdict="invalid"
        )


def test_strategy_memory_rejected_requires_reason():
    """Verdict='rejected' requires rejection_reason."""
    # Pydantic v2 runs validators in definition order; rejection_reason
    # comes after verdict, so the cross-field validator fires correctly.
    s = StrategyMemory(
        strategy_name="S",
        strategy_type="momentum",
        hypothesis="h",
        verdict="rejected",
        rejection_reason="Too volatile.",
    )
    assert s.verdict == "rejected"
    assert s.rejection_reason == "Too volatile."


# ---------------------------------------------------------------------------
# 3. Store initialization
# ---------------------------------------------------------------------------


def test_store_initialize(temp_store):
    """Store initializes without error; tables exist."""
    stats = temp_store.stats()
    assert "agent_memory" in stats
    assert "strategy_memory" in stats
    assert "handoffs" in stats
    assert "risk_decisions" in stats
    # All tables start at 0 rows
    assert all(v == 0 for v in stats.values())


# ---------------------------------------------------------------------------
# 4. Add and get memory
# ---------------------------------------------------------------------------


def test_add_and_get_memory(temp_store, sample_memory):
    """Add a MemoryRecord and retrieve it by ID."""
    added_id = temp_store.add_memory(sample_memory)
    assert added_id == sample_memory.id

    fetched = temp_store.get_memory(sample_memory.id)
    assert fetched is not None
    assert fetched.id == sample_memory.id
    assert fetched.agent_name == "architect"
    assert fetched.title == "Design module layout"
    assert fetched.content == "Created the memory module with store, journal, and retriever."
    assert fetched.memory_type == "agent_task"
    assert fetched.status == "active"
    assert fetched.tags == ["architecture", "memory"]
    assert fetched.importance_score == 0.5


# ---------------------------------------------------------------------------
# 5. list_recent ordering
# ---------------------------------------------------------------------------


def test_list_recent(temp_store):
    """Add 5 memories with staggered timestamps; list_recent(3) returns 3 most recent."""
    base_time = datetime.now(timezone.utc)
    for i in range(5):
        record = MemoryRecord(
            agent_name="agent",
            memory_type="agent_task",
            title=f"Task {i}",
            content=f"Content {i}",
            created_at=base_time - timedelta(minutes=(4 - i)),
            updated_at=base_time - timedelta(minutes=(4 - i)),
        )
        temp_store.add_memory(record)

    recent = temp_store.list_recent(3)
    assert len(recent) == 3
    # Most recent first
    assert recent[0].title == "Task 4"
    assert recent[1].title == "Task 3"
    assert recent[2].title == "Task 2"


# ---------------------------------------------------------------------------
# 6. search_by_agent
# ---------------------------------------------------------------------------


def test_search_by_agent(temp_store):
    """Add memories for two agents; search_by_agent filters correctly."""
    temp_store.add_memory(
        MemoryRecord(
            agent_name="architect",
            memory_type="agent_task",
            title="Design DB",
            content="Schema v1",
        )
    )
    temp_store.add_memory(
        MemoryRecord(
            agent_name="architect",
            memory_type="architecture_decision",
            title="Design API",
            content="REST v1",
        )
    )
    temp_store.add_memory(
        MemoryRecord(
            agent_name="executor",
            memory_type="agent_task",
            title="Run tests",
            content="pytest",
        )
    )
    temp_store.add_memory(
        MemoryRecord(
            agent_name="reviewer",
            memory_type="agent_task",
            title="Code review",
            content="LGTM",
        )
    )

    architect_memories = temp_store.search_by_agent("architect")
    assert len(architect_memories) == 2
    assert all(m.agent_name == "architect" for m in architect_memories)
    titles = {m.title for m in architect_memories}
    assert titles == {"Design DB", "Design API"}

    executor_memories = temp_store.search_by_agent("executor")
    assert len(executor_memories) == 1
    assert executor_memories[0].title == "Run tests"

    no_memories = temp_store.search_by_agent("nonexistent")
    assert no_memories == []


# ---------------------------------------------------------------------------
# 7. search_by_type
# ---------------------------------------------------------------------------


def test_search_by_type(temp_store):
    """Add memories of different types; search_by_type filters correctly."""
    temp_store.add_memory(
        MemoryRecord(agent_name="a", memory_type="agent_task", title="T1", content="c")
    )
    temp_store.add_memory(
        MemoryRecord(agent_name="a", memory_type="blocker", title="T2", content="c")
    )
    temp_store.add_memory(
        MemoryRecord(agent_name="a", memory_type="blocker", title="T3", content="c")
    )
    temp_store.add_memory(
        MemoryRecord(
            agent_name="a", memory_type="architecture_decision", title="T4", content="c"
        )
    )

    blockers = temp_store.search_by_type("blocker")
    assert len(blockers) == 2
    assert all(m.memory_type == "blocker" for m in blockers)

    tasks = temp_store.search_by_type("agent_task")
    assert len(tasks) == 1

    decisions = temp_store.search_by_type("architecture_decision")
    assert len(decisions) == 1


# ---------------------------------------------------------------------------
# 8. search_by_tags
# ---------------------------------------------------------------------------


def test_search_by_tags(temp_store):
    """Add memories with different tags; search_by_tags filters correctly."""
    temp_store.add_memory(
        MemoryRecord(
            agent_name="a",
            memory_type="agent_task",
            title="T1",
            content="c",
            tags=["architecture", "memory"],
        )
    )
    temp_store.add_memory(
        MemoryRecord(
            agent_name="a",
            memory_type="agent_task",
            title="T2",
            content="c",
            tags=["architecture", "testing"],
        )
    )
    temp_store.add_memory(
        MemoryRecord(
            agent_name="a", memory_type="agent_task", title="T3", content="c", tags=["testing"]
        )
    )
    temp_store.add_memory(
        MemoryRecord(agent_name="a", memory_type="agent_task", title="T4", content="c", tags=[])
    )

    arch_results = temp_store.search_by_tags(["architecture"])
    assert len(arch_results) == 2
    titles = {m.title for m in arch_results}
    assert titles == {"T1", "T2"}

    testing_results = temp_store.search_by_tags(["testing"])
    assert len(testing_results) == 2
    assert all("testing" in m.tags for m in testing_results)

    multi_results = temp_store.search_by_tags(["architecture", "testing"])
    assert len(multi_results) >= 2  # OR logic

    empty_results = temp_store.search_by_tags(["nonexistent"])
    assert empty_results == []


# ---------------------------------------------------------------------------
# 9. update_memory
# ---------------------------------------------------------------------------


def test_update_memory(temp_store, sample_memory):
    """Add a memory, update title and content; verify persistence."""
    temp_store.add_memory(sample_memory)
    original_updated_at = sample_memory.updated_at

    # Small delay to ensure updated_at changes
    time.sleep(0.05)

    ok = temp_store.update_memory(
        sample_memory.id, title="Updated Title", content="Updated content."
    )
    assert ok is True

    # Re-fetch from DB to confirm persistence
    fetched = temp_store.get_memory(sample_memory.id)
    assert fetched.title == "Updated Title"
    assert fetched.content == "Updated content."
    # Fields not updated should remain
    assert fetched.agent_name == "architect"
    assert fetched.memory_type == "agent_task"
    # updated_at should change
    assert fetched.updated_at > original_updated_at


def test_update_memory_tags(temp_store):
    """Update tags specifically."""
    record = MemoryRecord(
        agent_name="a", memory_type="agent_task", title="T", content="c", tags=["old"]
    )
    temp_store.add_memory(record)
    ok = temp_store.update_memory(record.id, tags=["new1", "new2"])
    assert ok is True
    fetched = temp_store.get_memory(record.id)
    assert fetched.tags == ["new1", "new2"]


# ---------------------------------------------------------------------------
# 10. resolve_memory
# ---------------------------------------------------------------------------


def test_resolve_memory(temp_store):
    """Add a memory with status 'active'; resolve_memory sets it to 'resolved'."""
    record = MemoryRecord(
        agent_name="a",
        memory_type="blocker",
        title="Blocker X",
        content="issue",
        status="active",
    )
    temp_store.add_memory(record)
    assert record.status == "active"

    ok = temp_store.resolve_memory(record.id)
    assert ok is True

    fetched = temp_store.get_memory(record.id)
    assert fetched.status == "resolved"


# ---------------------------------------------------------------------------
# 11. add_and_get_strategy_memory
# ---------------------------------------------------------------------------


def test_add_and_get_strategy_memory(temp_store, sample_strategy):
    """Add a StrategyMemory and retrieve it; verify universe preserved."""
    added_id = temp_store.add_strategy_memory(sample_strategy)
    assert added_id == sample_strategy.id

    fetched = temp_store.get_strategy_memory(sample_strategy.id)
    assert fetched is not None
    assert fetched.strategy_name == "Momentum Breakout"
    assert fetched.strategy_type == "momentum"
    assert fetched.universe == ["AAPL", "MSFT", "GOOGL"]
    assert fetched.sharpe == 1.8
    assert fetched.max_drawdown == -0.12
    assert fetched.verdict == "accepted"


# ---------------------------------------------------------------------------
# 12. list_rejected_strategies
# ---------------------------------------------------------------------------


def test_list_rejected_strategies(temp_store):
    """Add 3 strategies (1 accepted, 2 rejected); list_rejected returns exactly 2."""
    temp_store.add_strategy_memory(
        StrategyMemory(
            strategy_name="Mean Reversion",
            strategy_type="mean_reversion",
            hypothesis="Mean reversion in large-caps.",
            universe=["TSLA"],
            verdict="accepted",
            lessons_learned="Profitable in backtests.",
        )
    )
    temp_store.add_strategy_memory(
        StrategyMemory(
            strategy_name="Scalping",
            strategy_type="momentum",
            hypothesis="Quick intraday moves.",
            universe=["SPY"],
            verdict="rejected",
            rejection_reason="Too many false signals.",
        )
    )
    temp_store.add_strategy_memory(
        StrategyMemory(
            strategy_name="Arbitrage",
            strategy_type="arbitrage",
            hypothesis="Cross-exchange price gaps.",
            universe=["BTC", "ETH"],
            verdict="rejected",
            rejection_reason="Execution costs too high.",
        )
    )

    rejected = temp_store.list_rejected_strategies()
    assert len(rejected) == 2
    names = {s.strategy_name for s in rejected}
    assert names == {"Scalping", "Arbitrage"}
    assert all(s.verdict == "rejected" for s in rejected)


# ---------------------------------------------------------------------------
# 13. add_handoff
# ---------------------------------------------------------------------------


def test_add_handoff(temp_store):
    """Add a HandoffRecord; verify retrieved correctly."""
    record = HandoffRecord(
        from_agent="architect",
        to_agent="executor",
        task="Implement memory module",
        context="Use SQLite for persistence, Pydantic for models.",
    )
    added_id = temp_store.add_handoff(record)
    assert added_id == record.id

    fetched = temp_store.get_handoff(record.id)
    assert fetched is not None
    assert fetched.from_agent == "architect"
    assert fetched.to_agent == "executor"
    assert fetched.task == "Implement memory module"
    assert fetched.context == "Use SQLite for persistence, Pydantic for models."
    assert fetched.status == "pending"
    assert fetched.created_at is not None


# ---------------------------------------------------------------------------
# 14. add_risk_decision
# ---------------------------------------------------------------------------


def test_add_risk_decision(temp_store):
    """Add a RiskDecision; verify severity stored."""
    record = RiskDecision(
        agent_name="risk_manager",
        object_type="strategy",
        object_id="momentum_001",
        decision="rejected",
        reason="Exceeded max drawdown threshold.",
        severity="high",
    )
    added_id = temp_store.add_risk_decision(record)
    assert added_id == record.id

    fetched = temp_store.get_risk_decision(record.id)
    assert fetched is not None
    assert fetched.agent_name == "risk_manager"
    assert fetched.object_type == "strategy"
    assert fetched.object_id == "momentum_001"
    assert fetched.decision == "rejected"
    assert fetched.reason == "Exceeded max drawdown threshold."
    assert fetched.severity == "high"


# ---------------------------------------------------------------------------
# 15. memory_not_found
# ---------------------------------------------------------------------------


def test_memory_not_found(temp_store):
    """get_memory with a nonexistent ID returns None."""
    result = temp_store.get_memory("nonexistent-id-12345")
    assert result is None


def test_strategy_memory_not_found(temp_store):
    """get_strategy_memory with a nonexistent ID returns None."""
    result = temp_store.get_strategy_memory("nonexistent-id-12345")
    assert result is None


def test_handoff_not_found(temp_store):
    """get_handoff with a nonexistent ID returns None."""
    result = temp_store.get_handoff("nonexistent-id-12345")
    assert result is None


def test_risk_decision_not_found(temp_store):
    """get_risk_decision with a nonexistent ID returns None."""
    result = temp_store.get_risk_decision("nonexistent-id-12345")
    assert result is None


# ---------------------------------------------------------------------------
# Bonus: Store stats
# ---------------------------------------------------------------------------


def test_store_stats(temp_store, sample_memory, sample_strategy):
    """stats() returns accurate row counts."""
    stats0 = temp_store.stats()
    assert stats0["agent_memory"] == 0

    temp_store.add_memory(sample_memory)
    stats1 = temp_store.stats()
    assert stats1["agent_memory"] == 1

    temp_store.add_strategy_memory(sample_strategy)
    stats2 = temp_store.stats()
    assert stats2["strategy_memory"] == 1


# ---------------------------------------------------------------------------
# Bonus: get_memories flexible query
# ---------------------------------------------------------------------------


def test_get_memories_flexible(temp_store):
    """get_memories filters by agent_name, memory_type, and status."""
    temp_store.add_memory(
        MemoryRecord(
            agent_name="architect",
            memory_type="architecture_decision",
            title="D1",
            content="c",
            status="active",
        )
    )
    temp_store.add_memory(
        MemoryRecord(
            agent_name="architect",
            memory_type="architecture_decision",
            title="D2",
            content="c",
            status="resolved",
        )
    )
    temp_store.add_memory(
        MemoryRecord(
            agent_name="executor", memory_type="agent_task", title="T1", content="c"
        )
    )

    all_arch = temp_store.get_memories(agent_name="architect")
    assert len(all_arch) == 2

    decisions = temp_store.get_memories(
        agent_name="architect", memory_type="architecture_decision"
    )
    assert len(decisions) == 2

    active_only = temp_store.get_memories(
        agent_name="architect", status="active"
    )
    assert len(active_only) == 1
    assert active_only[0].title == "D1"


# ---------------------------------------------------------------------------
# Bonus: Context manager
# ---------------------------------------------------------------------------


def test_store_context_manager():
    """MemoryStore works as a context manager."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.duckdb")
        with MemoryStore(db_path) as store:
            store.initialize()
            assert store.stats() is not None
        # After exiting context, connection should be closed
