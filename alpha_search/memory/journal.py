"""AgentJournal — dual-write system: structured DB + human-readable Markdown.

Every log entry is written to both the DuckDB-backed MemoryStore and a
Markdown file. This gives agents fast structured queries (DB) while
keeping a human-readable audit trail (Markdown).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from alpha_search.memory.models import (
    HandoffRecord,
    MemoryRecord,
    RiskDecision,
    StrategyMemory,
)
from alpha_search.memory.store import MemoryStore


def _utc_timestamp() -> str:
    """Return a UTC timestamp string for Markdown headers."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _status_map(status: str) -> str:
    """Map user-facing status strings to DB-allowed values.

    DB allows: active, resolved, rejected, archived.
    """
    mapping = {
        "pending": "active",
        "in_progress": "active",
        "completed": "resolved",
        "done": "resolved",
        "failed": "rejected",
        "open": "active",
    }
    return mapping.get(status, status)


def _append_to_file(path: str, text: str) -> None:
    """Atomically append text to a file, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(text)
        fh.write("\n\n")


class AgentJournal:
    """Dual-write agent journal: structured DB + human-readable Markdown."""

    def __init__(self, store: MemoryStore, journal_dir: str = "memory") -> None:
        self.store = store
        self.journal_dir = journal_dir
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create memory directory and subdirectories."""
        os.makedirs(self.journal_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Task logging
    # ------------------------------------------------------------------
    def log_task(
        self,
        agent_name: str,
        task: str,
        status: str,
        notes: str = "",
        tags: Optional[list] = None,
    ) -> None:
        """Log a task entry to both DB and Markdown.

        DB: MemoryRecord with memory_type="agent_task"
        Markdown: appends to ``memory/agent_journal.md``
        """
        tags = tags or []
        ts = _utc_timestamp()
        db_status = _status_map(status)

        # --- Structured DB write ---
        record = MemoryRecord(
            agent_name=agent_name,
            memory_type="agent_task",
            title=task,
            content=notes,
            status=db_status,
            tags=tags,
        )
        self.store.add_memory(record)

        # --- Markdown write ---
        tags_line = f"Tags: {', '.join(tags)}" if tags else ""
        md = (
            f"### [{ts}] {agent_name} — {task} ({status})\n"
            f"\n"
            f"{notes}\n"
            f"\n"
            f"{tags_line}\n"
            f"---"
        )
        _append_to_file(os.path.join(self.journal_dir, "agent_journal.md"), md)

    # ------------------------------------------------------------------
    # Decision logging
    # ------------------------------------------------------------------
    def log_decision(
        self,
        agent_name: str,
        decision: str,
        rationale: str = "",
        tags: Optional[list] = None,
        importance_score: float = 0.7,
    ) -> None:
        """Log an architecture decision to both DB and Markdown.

        DB: MemoryRecord with memory_type="architecture_decision"
        Markdown: appends to ``memory/architecture_decisions.md``
        """
        tags = tags or []
        ts = _utc_timestamp()

        # --- Structured DB write ---
        record = MemoryRecord(
            agent_name=agent_name,
            memory_type="architecture_decision",
            title=decision,
            content=rationale,
            status="resolved",
            importance_score=importance_score,
            tags=tags,
        )
        self.store.add_memory(record)

        # --- Markdown write ---
        tags_line = f"Tags: {', '.join(tags)}" if tags else ""
        md = (
            f"### [{ts}] {agent_name}\n"
            f"\n"
            f"**Decision:** {decision}\n"
            f"\n"
            f"**Rationale:** {rationale}\n"
            f"\n"
            f"**Importance:** {importance_score:.1f}/1.0\n"
            f"\n"
            f"{tags_line}\n"
            f"---"
        )
        _append_to_file(
            os.path.join(self.journal_dir, "architecture_decisions.md"), md
        )

    # ------------------------------------------------------------------
    # Blocker logging
    # ------------------------------------------------------------------
    def log_blocker(
        self,
        agent_name: str,
        blocker: str,
        severity: str = "medium",
        tags: Optional[list] = None,
    ) -> None:
        """Log a blocker to both DB and Markdown.

        DB: MemoryRecord with memory_type="blocker"
        Markdown: appends to ``memory/agent_journal.md``

        Entry format includes severity indicator:
        🔴 high, 🟡 medium, 🟢 low.
        """
        tags = tags or []
        ts = _utc_timestamp()
        severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
            severity, "⚪"
        )

        # --- Structured DB write ---
        record = MemoryRecord(
            agent_name=agent_name,
            memory_type="blocker",
            title=blocker,
            content=f"Severity: {severity}",
            status="active",
            tags=tags,
        )
        self.store.add_memory(record)

        # --- Markdown write ---
        tags_line = f"Tags: {', '.join(tags)}" if tags else ""
        md = (
            f"### [{ts}] {severity_emoji} Blocker: {agent_name}\n"
            f"\n"
            f"**Blocker:** {blocker}\n"
            f"\n"
            f"**Severity:** {severity}\n"
            f"\n"
            f"{tags_line}\n"
            f"---"
        )
        _append_to_file(os.path.join(self.journal_dir, "agent_journal.md"), md)

    # ------------------------------------------------------------------
    # Handoff logging
    # ------------------------------------------------------------------
    def log_handoff(
        self,
        from_agent: str,
        to_agent: str,
        task: str,
        context: str = "",
    ) -> None:
        """Log an agent handoff to both DB and Markdown.

        DB: HandoffRecord
        Markdown: appends to ``memory/agent_journal.md``
        """
        ts = _utc_timestamp()

        # --- Structured DB write ---
        record = HandoffRecord(
            from_agent=from_agent,
            to_agent=to_agent,
            task=task,
            context=context,
            status="pending",
        )
        self.store.add_handoff(record)

        # --- Markdown write ---
        md = (
            f"### [{ts}] Handoff: {from_agent} → {to_agent}\n"
            f"\n"
            f"**Task:** {task}\n"
            f"\n"
            f"**Context:** {context}\n"
            f"\n"
            f"Status: pending\n"
            f"---"
        )
        _append_to_file(os.path.join(self.journal_dir, "agent_journal.md"), md)

    # ------------------------------------------------------------------
    # Strategy result logging
    # ------------------------------------------------------------------
    def log_strategy_result(self, strategy_memory: StrategyMemory) -> None:
        """Log a strategy result to both DB and Markdown.

        DB: StrategyMemory via ``store.add_strategy_memory()``
        Markdown: appends to ``memory/strategy_findings.md``

        Entry format includes verdict badge:
        ✅ accepted, ❌ rejected, 👀 watch, 🧪 needs testing.
        """
        # --- Structured DB write ---
        self.store.add_strategy_memory(strategy_memory)

        # --- Markdown write ---
        md = _strategy_to_markdown(strategy_memory)
        _append_to_file(
            os.path.join(self.journal_dir, "strategy_findings.md"), md
        )

    # ------------------------------------------------------------------
    # Risk decision logging
    # ------------------------------------------------------------------
    def log_risk_decision(
        self,
        agent_name: str,
        object_type: str,
        object_id: str,
        decision: str,
        reason: str,
        severity: str = "medium",
    ) -> None:
        """Log a risk decision to both DB and Markdown.

        DB: RiskDecision
        Markdown: appends to ``memory/risk_log.md``

        Entry format includes severity badge.
        """
        ts = _utc_timestamp()
        severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(
            severity, "⚪"
        )

        # --- Structured DB write ---
        record = RiskDecision(
            agent_name=agent_name,
            object_type=object_type,
            object_id=object_id,
            decision=decision,
            reason=reason,
            severity=severity,
        )
        self.store.add_risk_decision(record)

        # --- Markdown write ---
        decision_badge = {
            "approved": "✅",
            "rejected": "🚫",
            "flagged": "🚩",
            "deferred": "⏳",
            "escalated": "📢",
        }.get(decision, "❓")
        md = (
            f"### [{ts}] {severity_emoji} {agent_name}\n"
            f"\n"
            f"**Decision:** {decision_badge} {decision.upper()}\n"
            f"**Object:** `{object_type}` — `{object_id}`\n"
            f"**Severity:** {severity}\n"
            f"\n"
            f"**Reason:** {reason}\n"
            f"---"
        )
        _append_to_file(os.path.join(self.journal_dir, "risk_log.md"), md)


# ------------------------------------------------------------------
# Markdown formatting helpers
# ------------------------------------------------------------------

def _strategy_to_markdown(s: StrategyMemory) -> str:
    """Render a StrategyMemory as Markdown for strategy_findings.md."""
    ts = s.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    badge = {
        "accepted": "✅ accepted",
        "rejected": "❌ rejected",
        "watch": "👀 watch",
        "needs_more_testing": "🧪 needs testing",
    }.get(s.verdict, f"❓ {s.verdict}")

    lines = [
        f"### [{ts}] {s.strategy_name}",
        "",
        f"**Verdict:** {badge}",
        f"**Type:** {s.strategy_type} | **Market:** {s.market} | **Asset:** {s.asset_class}",
        "",
    ]
    if s.hypothesis:
        lines.append(f"**Hypothesis:** {s.hypothesis}")
    if s.result_summary:
        lines.append(f"**Result Summary:** {s.result_summary}")
    lines.append("")
    lines.append("**Metrics:**")
    metrics = s.key_metrics()
    for k, v in metrics.items():
        if v is not None:
            if k == "max_drawdown":
                lines.append(f"- {k}: {v:.2%}")
            else:
                lines.append(f"- {k}: {v:.4f}")
    if s.rejection_reason:
        lines.extend(["", f"**Rejection Reason:** {s.rejection_reason}"])
    if s.lessons_learned:
        lines.extend(["", f"**Lessons Learned:** {s.lessons_learned}"])
    lines.extend(["", "---"])
    return "\n".join(lines)
