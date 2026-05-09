"""MemoryRetriever — builds plain-text context for LLM agent prompts.

Aggregates multi-source memory (decisions, blockers, strategies, handoffs,
risk decisions) into formatted strings designed for injection into LLM
prompts. All methods return plain text.
"""

from __future__ import annotations

from typing import Optional

from alpha_search.memory.models import MemoryRecord, StrategyMemory
from alpha_search.memory.store import MemoryStore


class MemoryRetriever:
    """Retrieves memory context for agent prompts."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    # ------------------------------------------------------------------
    # Agent-scoped context
    # ------------------------------------------------------------------
    def get_agent_context(self, agent_name: str, limit: int = 10) -> str:
        """Return formatted context for a specific agent.

        Sections:
        - Recent decisions by this agent
        - Recent tasks by this agent
        - Unfinished (active) work
        """
        lines: list[str] = [f"Agent context for {agent_name}:", ""]

        # Recent decisions by this agent
        all_memories = self.store.search_by_agent(agent_name, limit=limit * 2)
        decisions = [m for m in all_memories if m.memory_type == "architecture_decision"]
        if decisions:
            lines.append(f"Recent decisions by {agent_name}:")
            for d in decisions[:limit]:
                score_str = f", score={d.importance_score:.2f}" if d.importance_score else ""
                lines.append(
                    f"- [{d.memory_type}] {d.title} ({d.status}{score_str})"
                )
            lines.append("")

        # Recent tasks
        tasks = [m for m in all_memories if m.memory_type == "agent_task"]
        if tasks:
            lines.append("Recent tasks:")
            for t in tasks[:limit]:
                lines.append(f"- [{t.status}] {t.title}")
            lines.append("")

        # Unfinished work (status == "active")
        unfinished = [m for m in all_memories if m.status == "active"]
        if unfinished:
            lines.append("Unfinished work:")
            for u in unfinished[:limit]:
                lines.append(f"- [{u.status}] {u.title}")
            lines.append("")
        else:
            lines.append("No unfinished work.")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Project-wide context
    # ------------------------------------------------------------------
    def get_project_context(self, limit: int = 10) -> str:
        """Return formatted project-wide context.

        Sections:
        - Recent decisions
        - Key architecture decisions (high importance)
        - Unresolved blockers
        - Recent strategy results
        """
        lines: list[str] = ["Project memory:", ""]

        all_recent = self.store.list_recent(limit=limit * 2)

        # Recent decisions (architecture_decision type)
        decisions = [m for m in all_recent if m.memory_type == "architecture_decision"]
        if decisions:
            lines.append("Recent decisions:")
            for d in decisions[:limit]:
                score_str = (
                    f" (score={d.importance_score:.2f})"
                    if d.importance_score
                    else ""
                )
                lines.append(f"- [{d.memory_type}] {d.title}{score_str}")
            lines.append("")
        else:
            lines.append("No recent decisions recorded.")
            lines.append("")

        # Key architecture decisions (high importance)
        key_decisions = [
            d for d in decisions if d.importance_score >= 0.7
        ]
        if key_decisions:
            lines.append("Key architecture decisions:")
            for d in key_decisions[:limit]:
                lines.append(
                    f"- {d.title} (importance={d.importance_score:.2f})"
                )
            lines.append("")
        else:
            lines.append("No key architecture decisions recorded.")
            lines.append("")

        # Unresolved blockers (active status)
        blockers = self.store.search_by_type("blocker", limit=limit)
        open_blockers = [b for b in blockers if b.status == "active"]
        if open_blockers:
            lines.append("Unresolved blockers:")
            for b in open_blockers:
                lines.append(f"- {b.agent_name}: {b.title}")
            lines.append("")
        else:
            lines.append("No unresolved blockers.")
            lines.append("")

        # Recent strategy results
        strategies = self.store.list_strategy_results(limit=limit)
        if strategies:
            lines.append("Recent strategy results:")
            for s in strategies:
                badge = {
                    "accepted": "✅",
                    "rejected": "❌",
                    "watch": "👀",
                    "needs_more_testing": "🧪",
                }.get(s.verdict, "❓")
                lines.append(
                    f"- {badge} {s.strategy_name} ({s.strategy_type})"
                )
            lines.append("")
        else:
            lines.append("No strategy results recorded.")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Strategy lessons
    # ------------------------------------------------------------------
    def get_strategy_lessons(self, strategy_type: str, limit: int = 10) -> str:
        """Return formatted strategy lessons for a given strategy type.

        Sections:
        - Accepted strategies
        - Rejected strategies
        - Lessons learned
        """
        lines: list[str] = [f"Strategy lessons ({strategy_type}):", ""]

        all_strategies = self.store.list_strategy_results(
            strategy_type=strategy_type, limit=limit * 2
        )

        accepted = [s for s in all_strategies if s.verdict == "accepted"]
        if accepted:
            lines.append("Accepted:")
            for s in accepted[:limit]:
                sharpe_str = f"sharpe={s.sharpe:.2f}" if s.sharpe is not None else ""
                lines.append(f"- {s.strategy_name} ({sharpe_str}) — {s.lessons_learned}")
            lines.append("")
        else:
            lines.append("Accepted: none yet")
            lines.append("")

        rejected = [s for s in all_strategies if s.verdict == "rejected"]
        if rejected:
            lines.append("Rejected:")
            for s in rejected[:limit]:
                dd_str = ""
                if s.max_drawdown is not None:
                    dd_str = f"drawdown={s.max_drawdown:.2%}"
                reason = s.rejection_reason or s.lessons_learned or ""
                lines.append(f"- {s.strategy_name} ({dd_str}) — {reason}")
            lines.append("")
        else:
            lines.append("Rejected: none yet")
            lines.append("")

        # Lessons learned from all results
        if all_strategies:
            lines.append("Lessons learned:")
            seen: set[str] = set()
            for s in all_strategies:
                lesson = (s.lessons_learned or s.rejection_reason or "").strip()
                if lesson and lesson.lower() not in seen:
                    seen.add(lesson.lower())
                    lines.append(f"- [{s.verdict.upper()}] {lesson}")
            lines.append("")
        else:
            lines.append("Lessons learned: none recorded yet")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Unresolved blockers
    # ------------------------------------------------------------------
    def get_unresolved_blockers(self, limit: int = 10) -> str:
        """Return a plain-text list of unresolved blockers."""
        blockers = self.store.search_by_type("blocker", limit=limit)
        open_blockers = [b for b in blockers if b.status == "active"]
        if not open_blockers:
            return "Unresolved blockers: none\n"

        lines: list[str] = ["Unresolved blockers:"]
        for b in open_blockers:
            lines.append(f"- {b.agent_name}: {b.title}")
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Recent decisions
    # ------------------------------------------------------------------
    def get_recent_decisions(self, limit: int = 10) -> str:
        """Return a plain-text list of recent architecture decisions."""
        all_recent = self.store.list_recent(limit=limit * 2)
        decisions = [
            m for m in all_recent if m.memory_type == "architecture_decision"
        ]
        if not decisions:
            return "Recent decisions: none\n"

        lines: list[str] = ["Recent decisions:"]
        for d in decisions[:limit]:
            score_str = (
                f" (score={d.importance_score:.2f})"
                if d.importance_score
                else ""
            )
            lines.append(f"- [{d.memory_type}] {d.title}{score_str}")
        lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Full prompt context assembly
    # ------------------------------------------------------------------
    def build_agent_prompt_context(self, agent_name: str) -> str:
        """Combine all context sources into one comprehensive prompt string.

        Returns a single plain-text block with sections for:
        - Project context
        - Agent-specific context
        - Unresolved blockers
        - Strategy lessons (all types)
        """
        sections: list[str] = [
            "=== Alpha Search Agent Context ===",
            f"Agent: {agent_name}",
            "",
        ]

        # Project-wide context
        sections.append(self.get_project_context(limit=10))

        # Agent-specific context
        sections.append(self.get_agent_context(agent_name=agent_name, limit=10))

        # Unresolved blockers
        sections.append(self.get_unresolved_blockers(limit=10))

        # Strategy lessons for each major type
        for st in ["mean_reversion", "momentum", "arbitrage", "event_driven"]:
            sections.append(self.get_strategy_lessons(strategy_type=st, limit=5))

        sections.append("=== End Context ===")
        return "\n".join(sections)

    # ------------------------------------------------------------------
    # Raw record access (for advanced use)
    # ------------------------------------------------------------------
    def get_raw_memories(
        self,
        agent_name: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        """Return raw MemoryRecord objects for programmatic use."""
        if agent_name:
            return self.store.search_by_agent(agent_name, limit=limit)
        if memory_type:
            return self.store.search_by_type(memory_type, limit=limit)
        return self.store.list_recent(limit=limit)

    def get_raw_strategies(
        self,
        strategy_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[StrategyMemory]:
        """Return raw StrategyMemory objects for programmatic use."""
        return self.store.list_strategy_results(
            strategy_type=strategy_type, limit=limit
        )
