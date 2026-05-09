"""Alpha Search Memory Layer - Persistent agent memory with dual-write journaling.

Uses DuckDB (with SQLite fallback) for structured storage and Markdown files
for human-readable memory journals. Provides durable memory across sessions
for agents to remember decisions, strategy results, failures, blockers,
handoffs, architecture choices, and research findings.

Modules:
    models  -- Pydantic data models (MemoryRecord, StrategyMemory, HandoffRecord, RiskDecision)
    store   -- DuckDB/SQLite-backed MemoryStore with CRUD operations
    journal -- AgentJournal dual-write (DB + Markdown) logging system
    retrieval -- MemoryRetriever for building LLM prompt context
"""

from __future__ import annotations

from alpha_search.memory.models import (
    HandoffRecord,
    MemoryRecord,
    RiskDecision,
    StrategyMemory,
)
from alpha_search.memory.store import MemoryStore
from alpha_search.memory.journal import AgentJournal
from alpha_search.memory.retrieval import MemoryRetriever

__all__ = [
    "MemoryRecord",
    "StrategyMemory",
    "HandoffRecord",
    "RiskDecision",
    "MemoryStore",
    "AgentJournal",
    "MemoryRetriever",
]
