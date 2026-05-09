"""Alpha Search Memory Layer \u2014 Pydantic models for agent memory, strategy results,
handoffs, and risk decisions.

All models use Pydantic v2 (BaseModel, Field, field_validator) with real
validators, full type hints, and DuckDB-compatible serialization.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Constants ────────────────────────────────────────────────────────────────

MEMORY_TYPES = Literal[
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
]

MEMORY_TYPE_VALUES = {
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
}

STATUS_VALUES = {"active", "resolved", "rejected", "archived"}
STATUS_TYPE = Literal["active", "resolved", "rejected", "archived"]

VERDICT_VALUES = {"accepted", "rejected", "watch", "needs_more_testing"}
VERDICT_TYPE = Literal["accepted", "rejected", "watch", "needs_more_testing"]

STRATEGY_TYPES = Literal["momentum", "mean_reversion", "arbitrage", "event_driven", "portfolio"]
STRATEGY_TYPE_VALUES = {"momentum", "mean_reversion", "arbitrage", "event_driven", "portfolio"}

HANDOFF_STATUS_VALUES = {"pending", "in_progress", "completed", "failed"}
HANDOFF_STATUS_TYPE = Literal["pending", "in_progress", "completed", "failed"]

SEVERITY_VALUES = {"info", "low", "medium", "high", "critical"}
SEVERITY_TYPE = Literal["info", "low", "medium", "high", "critical"]


# ══════════════════════════════════════════════════════════════════════════════
# MemoryRecord
# ══════════════════════════════════════════════════════════════════════════════


class MemoryRecord(BaseModel):
    """A single memory entry for an agent \u2014 decisions, tasks, blockers, findings."""

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    # ── Fields ───────────────────────────────────────────────────────────────

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique record UUID")
    agent_name: str = Field(..., description="Name of the agent that created this memory")
    memory_type: str = Field(
        ...,
        description="Category of memory \u2014 must be one of the allowed values",
    )
    title: str = Field(..., min_length=1, description="Short human-readable title")
    content: str = Field(default="", description="Full content / notes / body")
    tags: list[str] = Field(default_factory=list, description="Free-form tags for filtering")
    importance_score: float = Field(
        default=0.5, description="0.0 = trivia, 1.0 = critical (auto-clamped)"
    )
    status: STATUS_TYPE = Field(default="active", description="Lifecycle state of the memory")
    source_file: Optional[str] = Field(default=None, description="Optional source file reference")
    related_task: Optional[str] = Field(default=None, description="Optional related task ID")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC last-update timestamp"
    )

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("memory_type")
    @classmethod
    def _validate_memory_type(cls, value: str) -> str:
        """Ensure memory_type is one of the allowed categories."""
        if value not in MEMORY_TYPE_VALUES:
            allowed = ", ".join(sorted(MEMORY_TYPE_VALUES))
            raise ValueError(f"memory_type must be one of: {allowed}. Got: {value!r}")
        return value

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: str) -> str:
        """Ensure status is a recognized lifecycle value."""
        if value not in STATUS_VALUES:
            allowed = ", ".join(sorted(STATUS_VALUES))
            raise ValueError(f"status must be one of: {allowed}. Got: {value!r}")
        return value

    @field_validator("importance_score")
    @classmethod
    def _clamp_importance(cls, value: float) -> float:
        """Clamp importance_score to [0.0, 1.0]."""
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return round(value, 4)

    @field_validator("updated_at")
    @classmethod
    def _sync_updated_at(cls, value: datetime, info: Any) -> datetime:
        """On creation, ensure updated_at matches created_at if not explicitly set."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @field_validator("created_at")
    @classmethod
    def _ensure_tz_created(cls, value: datetime) -> datetime:
        """Ensure created_at is timezone-aware (UTC if naive)."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    # ── Methods ──────────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a fully serialisable dict with ISO-8601 datetime strings.

        Suitable for JSON serialization or DuckDB row insertion.
        """
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "memory_type": self.memory_type,
            "title": self.title,
            "content": self.content,
            "tags": json.dumps(self.tags),
            "importance_score": self.importance_score,
            "status": self.status,
            "source_file": self.source_file,
            "related_task": self.related_task,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_row(self) -> dict[str, Any]:
        """Return a dict keyed to the DB column layout used by store.py."""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "memory_type": self.memory_type,
            "content": self.content,
            "tags": json.dumps(self.tags),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    # Alias properties used by retrieval.py
    @property
    def score(self) -> float:
        """Alias for ``importance_score`` (used by retrievers)."""
        return self.importance_score

    @property
    def meta(self) -> dict[str, Any]:
        """Structured metadata extracted from tags or content (used by retrievers)."""
        return {"severity": "medium"}

    @classmethod
    def from_row(cls, row: tuple) -> "MemoryRecord":
        """Rehydrate from a database row tuple.

        Args:
            row: Tuple of (id, agent_name, memory_type, title, content,
                tags, importance_score, status, source_file, related_task,
                created_at, updated_at).
        """
        return cls(
            id=row[0],
            agent_name=row[1],
            memory_type=row[2],
            title=row[3],
            content=row[4] or "",
            tags=json.loads(row[5]) if row[5] else [],
            importance_score=float(row[6]) if row[6] is not None else 0.5,
            status=row[7],
            source_file=row[8],
            related_task=row[9],
            created_at=_parse_iso(row[10]),
            updated_at=_parse_iso(row[11]),
        )

    def summary(self) -> str:
        """One-line summary: ``[memory_type] title (status, importance)``."""
        return f"[{self.memory_type}] {self.title} ({self.status}, {self.importance_score:.2f})"

    def touch(self) -> None:
        """Update the ``updated_at`` timestamp to now (UTC)."""
        self.updated_at = datetime.now(timezone.utc)

    def __str__(self) -> str:
        return self.summary()

    def __repr__(self) -> str:
        return (
            f"MemoryRecord(id={self.id!r}, memory_type={self.memory_type!r}, "
            f"title={self.title!r}, status={self.status!r})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# StrategyMemory
# ══════════════════════════════════════════════════════════════════════════════


class StrategyMemory(BaseModel):
    """Full record of a strategy backtest / evaluation result for long-term
    agent memory.  Captures hypothesis, metrics, verdict, and lessons learned.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    # ── Fields ───────────────────────────────────────────────────────────────

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique record UUID")
    strategy_name: str = Field(..., description="Human-readable strategy name")
    strategy_type: str = Field(
        ...,
        description="Strategy family: momentum, mean_reversion, arbitrage, event_driven, portfolio",
    )
    market: str = Field(default="global", description="Market scope, e.g. 'US', 'EM', 'global'")
    asset_class: str = Field(default="equity", description="Primary asset class")
    universe: list[str] = Field(default_factory=list, description="Tickers / identifiers in universe")
    hypothesis: str = Field(..., description="What the strategy is trying to exploit")
    result_summary: str = Field(default="", description="Executive summary of backtest results")
    sharpe: Optional[float] = Field(default=None, description="Annualised Sharpe ratio (auto-clamped to [-10, 10])")
    max_drawdown: Optional[float] = Field(default=None, ge=-1.0, le=1.0, description="Maximum drawdown as positive decimal (e.g. 0.18 = 18% drawdown)")
    total_return: Optional[float] = Field(default=None, description="Total return over backtest period")
    win_rate: Optional[float] = Field(default=None, description="Win rate fraction [0, 1] (auto-clamped)")
    turnover: Optional[float] = Field(default=None, ge=0.0, description="Annual turnover estimate")
    transaction_cost_assumption: Optional[str] = Field(
        default=None, description="Description of cost assumptions used"
    )
    validation_method: str = Field(
        default="", description="How the strategy was validated (walk-forward, CV, OOS, etc.)"
    )
    verdict: VERDICT_TYPE = Field(default="watch", description="Final evaluation verdict")
    rejection_reason: Optional[str] = Field(default=None, description="Why rejected (required when verdict='rejected')")
    lessons_learned: str = Field(default="", description="Key take-aways for future strategies")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC creation timestamp"
    )

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("strategy_type")
    @classmethod
    def _validate_strategy_type(cls, value: str) -> str:
        """Ensure strategy_type is a recognized family."""
        if value not in STRATEGY_TYPE_VALUES:
            allowed = ", ".join(sorted(STRATEGY_TYPE_VALUES))
            raise ValueError(f"strategy_type must be one of: {allowed}. Got: {value!r}")
        return value

    @field_validator("verdict")
    @classmethod
    def _validate_verdict(cls, value: str) -> str:
        """Ensure verdict is a recognized evaluation outcome."""
        if value not in VERDICT_VALUES:
            allowed = ", ".join(sorted(VERDICT_VALUES))
            raise ValueError(f"verdict must be one of: {allowed}. Got: {value!r}")
        return value

    @field_validator("rejection_reason")
    @classmethod
    def _validate_rejection(cls, value: Optional[str], info: Any) -> Optional[str]:
        """Warn-level validation: rejection_reason should be present when verdict is 'rejected'."""
        data = info.data
        verdict = data.get("verdict")
        if verdict == "rejected" and (value is None or value.strip() == ""):
            raise ValueError("rejection_reason is required when verdict='rejected'")
        return value

    @field_validator("win_rate")
    @classmethod
    def _clamp_win_rate(cls, value: Optional[float]) -> Optional[float]:
        """Clamp win_rate to [0.0, 1.0] if provided."""
        if value is None:
            return None
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return round(value, 6)

    @field_validator("max_drawdown")
    @classmethod
    def _validate_drawdown(cls, value: Optional[float]) -> Optional[float]:
        """Max drawdown must be between -1.0 and 1.0 if provided."""
        if value is None:
            return None
        if value < -1.0 or value > 1.0:
            raise ValueError(f"max_drawdown must be between -1.0 and 1.0. Got: {value}")
        return round(abs(value), 6)

    @field_validator("sharpe")
    @classmethod
    def _clamp_sharpe(cls, value: Optional[float]) -> Optional[float]:
        """Clamp Sharpe to a realistic range [-10, 10] if provided."""
        if value is None:
            return None
        if value < -10.0:
            return -10.0
        if value > 10.0:
            return 10.0
        return round(value, 6)

    @field_validator("created_at")
    @classmethod
    def _ensure_tz_created(cls, value: datetime) -> datetime:
        """Ensure created_at is timezone-aware (UTC if naive)."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    # ── Methods ──────────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a fully serialisable dict with ISO-8601 datetime and JSON list fields."""
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type,
            "market": self.market,
            "asset_class": self.asset_class,
            "universe": json.dumps(self.universe),
            "hypothesis": self.hypothesis,
            "result_summary": self.result_summary,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "win_rate": self.win_rate,
            "turnover": self.turnover,
            "transaction_cost_assumption": self.transaction_cost_assumption,
            "validation_method": self.validation_method,
            "verdict": self.verdict,
            "rejection_reason": self.rejection_reason,
            "lessons_learned": self.lessons_learned,
            "created_at": self.created_at.isoformat(),
        }

    def to_row(self) -> dict[str, Any]:
        """Return a dict keyed to the DB column layout used by store.py."""
        return {
            "id": self.id,
            "strategy_type": self.strategy_type,
            "ticker": self.universe[0] if self.universe else "",
            "universe": json.dumps(self.universe),
            "verdict": self.verdict,
            "metrics": json.dumps(self.key_metrics()),
            "created_at": self.created_at.isoformat(),
        }

    # Alias properties used by retrieval.py
    @property
    def name(self) -> str:
        """Alias for ``strategy_name`` (used by retrievers)."""
        return self.strategy_name

    @property
    def rationale(self) -> str:
        """Rationale for the strategy verdict (used by retrievers)."""
        return self.rejection_reason or self.lessons_learned or self.result_summary or ""

    @property
    def metrics(self) -> dict[str, Any]:
        """Return metrics as a plain dict (used by retrievers)."""
        return self.key_metrics()

    def to_markdown(self) -> str:
        """Render this strategy result as a Markdown entry for the journal."""
        verdict_icons = {
            "accepted": "\u2705",
            "rejected": "\u274c",
            "watch": "\ud83d\udc40",
            "needs_more_testing": "\ud83e\uddea",
        }
        icon = verdict_icons.get(self.verdict, "\u2753")
        universe_str = ", ".join(self.universe) if self.universe else "N/A"
        metrics_lines = ""
        if self.sharpe is not None:
            metrics_lines += f"- **Sharpe:** {self.sharpe:.2f}\n"
        if self.max_drawdown is not None:
            metrics_lines += f"- **Max Drawdown:** {self.max_drawdown:.2%}\n"
        if self.total_return is not None:
            metrics_lines += f"- **Total Return:** {self.total_return:.2%}\n"
        return (
            f"### {icon} {self.strategy_name}\n\n"
            f"**Type:** {self.strategy_type} | **Market:** {self.market}\n\n"
            f"**Universe:** {universe_str}\n\n"
            f"{metrics_lines}"
            f"**Verdict:** {self.verdict}\n\n"
            f"{self.rationale}\n\n"
            f"---"
        )

    @classmethod
    def from_row(cls, row: tuple) -> "StrategyMemory":
        """Rehydrate from a database row tuple.

        Args:
            row: Tuple of (id, strategy_name, strategy_type, market,
                asset_class, universe, hypothesis, result_summary, sharpe,
                max_drawdown, total_return, win_rate, turnover,
                transaction_cost_assumption, validation_method, verdict,
                rejection_reason, lessons_learned, created_at).
        """
        return cls(
            id=row[0],
            strategy_name=row[1],
            strategy_type=row[2],
            market=row[3] or "global",
            asset_class=row[4] or "equity",
            universe=json.loads(row[5]) if row[5] else [],
            hypothesis=row[6] or "",
            result_summary=row[7] or "",
            sharpe=float(row[8]) if row[8] is not None else None,
            max_drawdown=float(row[9]) if row[9] is not None else None,
            total_return=float(row[10]) if row[10] is not None else None,
            win_rate=float(row[11]) if row[11] is not None else None,
            turnover=float(row[12]) if row[12] is not None else None,
            transaction_cost_assumption=row[13],
            validation_method=row[14] or "",
            verdict=row[15],
            rejection_reason=row[16],
            lessons_learned=row[17] or "",
            created_at=_parse_iso(row[18]),
        )

    def summary(self) -> str:
        """One-line summary: ``[verdict] strategy_name | market | validation_method``."""
        return f"[{self.verdict}] {self.strategy_name} | {self.market} | {self.validation_method}"

    def is_accepted(self) -> bool:
        """Return ``True`` if the strategy was accepted for deployment."""
        return self.verdict == "accepted"

    def is_rejected(self) -> bool:
        """Return ``True`` if the strategy was explicitly rejected."""
        return self.verdict == "rejected"

    def key_metrics(self) -> dict[str, Optional[float]]:
        """Return a dict of the core performance metrics."""
        return {
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "win_rate": self.win_rate,
            "turnover": self.turnover,
        }

    def __str__(self) -> str:
        return self.summary()

    def __repr__(self) -> str:
        return (
            f"StrategyMemory(id={self.id!r}, strategy_name={self.strategy_name!r}, "
            f"verdict={self.verdict!r}, sharpe={self.sharpe!r})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# HandoffRecord
# ══════════════════════════════════════════════════════════════════════════════


class HandoffRecord(BaseModel):
    """Records a task handoff from one agent to another \u2014 captures context
    so the receiving agent can pick up work seamlessly.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    # ── Fields ───────────────────────────────────────────────────────────────

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique handoff UUID")
    from_agent: str = Field(..., description="Agent handing off the task")
    to_agent: str = Field(..., description="Agent receiving the task")
    task: str = Field(..., min_length=1, description="Description of the task being handed off")
    context: str = Field(default="", description="Context, state, findings, and notes for the receiver")
    status: HANDOFF_STATUS_TYPE = Field(default="pending", description="Lifecycle of the handoff")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC creation timestamp"
    )

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("status")
    @classmethod
    def _validate_handoff_status(cls, value: str) -> str:
        """Ensure handoff status is a recognized value."""
        if value not in HANDOFF_STATUS_VALUES:
            allowed = ", ".join(sorted(HANDOFF_STATUS_VALUES))
            raise ValueError(f"status must be one of: {allowed}. Got: {value!r}")
        return value

    @field_validator("from_agent", "to_agent")
    @classmethod
    def _non_empty_agent(cls, value: str) -> str:
        """Agent names must be non-empty after stripping."""
        if not value or not value.strip():
            raise ValueError("Agent name must be a non-empty string")
        return value.strip()

    @field_validator("created_at")
    @classmethod
    def _ensure_tz_created(cls, value: datetime) -> datetime:
        """Ensure created_at is timezone-aware (UTC if naive)."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    # ── Methods ──────────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a fully serialisable dict with ISO-8601 datetime strings."""
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "task": self.task,
            "context": self.context,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

    def to_row(self) -> dict[str, Any]:
        """Return a dict keyed to the DB column layout used by store.py."""
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "context": self.context,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: tuple) -> "HandoffRecord":
        """Rehydrate from a database row tuple.

        Args:
            row: Tuple of (id, from_agent, to_agent, task, context,
                status, created_at).
        """
        return cls(
            id=row[0],
            from_agent=row[1],
            to_agent=row[2],
            task=row[3],
            context=row[4] or "",
            status=row[5],
            created_at=_parse_iso(row[6]),
        )

    def summary(self) -> str:
        """One-line summary: ``handoff: from_agent -> to_agent (status)``."""
        return f"handoff: {self.from_agent} -> {self.to_agent} ({self.status})"

    def complete(self) -> None:
        """Mark the handoff as completed."""
        self.status = "completed"

    def fail(self, context: str = "") -> None:
        """Mark the handoff as failed, optionally appending context."""
        self.status = "failed"
        if context:
            self.context = f"{self.context}\nFAILURE: {context}".strip()

    def __str__(self) -> str:
        return self.summary()

    def __repr__(self) -> str:
        return (
            f"HandoffRecord(id={self.id!r}, from_agent={self.from_agent!r}, "
            f"to_agent={self.to_agent!r}, status={self.status!r})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# RiskDecision
# ══════════════════════════════════════════════════════════════════════════════


class RiskDecision(BaseModel):
    """Records a risk-based decision made by an agent \u2014 e.g. rejecting a data
    source, flagging a strategy, or blocking a deployment.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    # ── Fields ───────────────────────────────────────────────────────────────

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique decision UUID")
    agent_name: str = Field(..., description="Agent that made the risk decision")
    object_type: str = Field(
        ...,
        description="Type of object being evaluated: strategy, data_source, model, pipeline, deployment",
    )
    object_id: str = Field(..., description="Identifier of the object being evaluated")
    decision: str = Field(
        ...,
        description="The decision taken: approved, rejected, flagged, escalated, deferred",
    )
    reason: str = Field(default="", description="Detailed rationale for the decision")
    severity: SEVERITY_TYPE = Field(default="medium", description="Risk severity level")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="UTC creation timestamp"
    )

    # ── Validators ───────────────────────────────────────────────────────────

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, value: str) -> str:
        """Ensure severity is a recognized level."""
        if value not in SEVERITY_VALUES:
            allowed = ", ".join(sorted(SEVERITY_VALUES))
            raise ValueError(f"severity must be one of: {allowed}. Got: {value!r}")
        return value

    @field_validator("decision")
    @classmethod
    def _validate_decision(cls, value: str) -> str:
        """Ensure decision is a recognized risk decision value."""
        allowed_decisions = {"approved", "rejected", "flagged", "escalated", "deferred"}
        if value not in allowed_decisions:
            allowed = ", ".join(sorted(allowed_decisions))
            raise ValueError(f"decision must be one of: {allowed}. Got: {value!r}")
        return value

    @field_validator("object_type")
    @classmethod
    def _validate_object_type(cls, value: str) -> str:
        """Ensure object_type is a recognized category."""
        allowed_types = {"strategy", "data_source", "model", "pipeline", "deployment", "signal"}
        if value not in allowed_types:
            allowed = ", ".join(sorted(allowed_types))
            raise ValueError(f"object_type must be one of: {allowed}. Got: {value!r}")
        return value

    @field_validator("agent_name", "object_id")
    @classmethod
    def _non_empty_string(cls, value: str) -> str:
        """Ensure string fields are non-empty after stripping."""
        if not value or not value.strip():
            raise ValueError("Field must be a non-empty string")
        return value.strip()

    @field_validator("created_at")
    @classmethod
    def _ensure_tz_created(cls, value: datetime) -> datetime:
        """Ensure created_at is timezone-aware (UTC if naive)."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    # ── Methods ──────────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return a fully serialisable dict with ISO-8601 datetime strings."""
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "decision": self.decision,
            "reason": self.reason,
            "severity": self.severity,
            "created_at": self.created_at.isoformat(),
        }

    def to_row(self) -> dict[str, Any]:
        """Return a dict keyed to the DB column layout used by store.py."""
        return {
            "id": self.id,
            "severity": self.severity,
            "decision": self.decision,
            "reasoning": self.reason,
            "ticker": self.object_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_row(cls, row: tuple) -> "RiskDecision":
        """Rehydrate from a database row tuple.

        Args:
            row: Tuple of (id, agent_name, object_type, object_id,
                decision, reason, severity, created_at).
        """
        return cls(
            id=row[0],
            agent_name=row[1],
            object_type=row[2],
            object_id=row[3],
            decision=row[4],
            reason=row[5] or "",
            severity=row[6],
            created_at=_parse_iso(row[7]),
        )

    def summary(self) -> str:
        """One-line summary: ``[severity] decision on object_type:object_id by agent_name``."""
        return f"[{self.severity}] {self.decision} on {self.object_type}:{self.object_id} by {self.agent_name}"

    def is_blocking(self) -> bool:
        """Return ``True`` if this decision blocks progress (rejected / escalated)."""
        return self.decision in ("rejected", "escalated")

    def __str__(self) -> str:
        return self.summary()

    def __repr__(self) -> str:
        return (
            f"RiskDecision(id={self.id!r}, agent_name={self.agent_name!r}, "
            f"decision={self.decision!r}, severity={self.severity!r})"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════


def _parse_iso(value: Any) -> datetime:
    """Parse an ISO-8601 datetime string, handling both aware and naive inputs.

    Args:
        value: String or datetime object.

    Returns:
        Timezone-aware UTC datetime.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        s = s.replace("Z", "+00:00")
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S.%f%z",
            "%Y-%m-%d %H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(s, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime: {value!r}")
    raise TypeError(f"Expected str or datetime, got {type(value)}")
