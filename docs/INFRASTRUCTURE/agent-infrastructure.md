# Multi-Agent Persistent Memory Architecture

> **Status:** Core architecture document
> **Applies to:** Alpha Search agent framework, research automation, multi-agent workflows
> **Last updated:** v0.1.0

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Memory Subsystems](#memory-subsystems)
3. [Task Orchestration](#task-orchestration)
4. [Inter-Agent Communication](#inter-agent-communication)
5. [Agent Lifecycle](#agent-lifecycle)
6. [Implementation Details](#implementation-details)
7. [Deployment Configuration](#deployment-configuration)
8. [Monitoring & Observability](#monitoring)

---

## Architecture Overview

Alpha Search uses a multi-agent architecture where specialized agents collaborate on quantitative research tasks. Each agent has persistent memory, enabling long-running research workflows that span multiple sessions.

### Design Principles

| Principle | Description |
|---|---|
| **Memory persistence** | Agent state survives restarts and crashes |
| **Structured + unstructured** | DuckDB for structured data, markdown for logs, ChromaDB for semantic search |
| **Decentralized coordination** | No single point of failure; agents communicate via message bus |
| **Observable** | All agent actions are logged and auditable |
| **Recoverable** | Failed tasks can be replayed from last checkpoint |

### System Architecture

```
+-------------------------------------------------------------------+
|                         Alpha Search Agent System                      |
|                                                                    |
|  +----------+  +----------+  +----------+  +----------+           |
|  | Research |  |  Market  |  |  Risk    |  | Portfolio|           |
|  |  Agent   |  |  Agent   |  |  Agent   |  |  Agent   |           |
|  +----+-----+  +----+-----+  +----+-----+  +----+-----+           |
|       |             |             |             |                 |
|       +-------------+------+------+-------------+                 |
|                            |                                       |
|                     +------v------+                                |
|                     |   Redis     |                                |
|                     |   Pub/Sub   |                                |
|                     +------+------+                                |
|                            |                                       |
|       +--------------------+--------------------+                  |
|       |                    |                    |                  |
|  +----v-----+       +------v------+     +------v------+           |
|  |  DuckDB  |       |  Markdown   |     |  ChromaDB   |           |
|  | (Tables) |       |  (Journals) |     | (Vectors)   |           |
|  |          |       |             |     |             |           |
|  | strategies      | agent logs    |     | embeddings  |           |
|  | backtest results| task history  |     | document    |           |
|  | market data     | decisions     |     | similarity  |           |
|  | agent state     | errors        |     | semantic    |           |
|  | portfolio snaps | reasoning     |     | search      |           |
|  +------------+----+------+--------+     +-------------+           |
|               |           |                                       |
|          +----v-----------v----+                                 |
|          |   Task Queue        |                                 |
|          |   (Redis Streams)   |                                 |
|          +---------------------+                                 |
+-------------------------------------------------------------------+
```

### Agent Types

| Agent | Role | Key Memory |
|---|---|---|
| **Research Agent** | Hypothesis generation, literature review | Research notes, paper references, hypothesis history |
| **Market Data Agent** | Data ingestion, cleaning, feature engineering | Data sources, schemas, transformation pipelines |
| **Strategy Agent** | Strategy implementation, parameter optimization | Strategy variants, optimization history, performance |
| **Backtest Agent** | Backtesting execution, result analysis | Backtest configurations, results, benchmark comparisons |
| **Risk Agent** | Risk analysis, drawdown monitoring, position sizing | Risk models, stress test results, VaR calculations |
| **Portfolio Agent** | Portfolio construction, rebalancing, allocation | Allocation history, rebalancing triggers, drift tracking |
| **Reporting Agent** | Report generation, visualization, alerting | Report templates, scheduled jobs, alert history |

---

## Memory Subsystems

### 1. DuckDB -- Structured Agent Memory

DuckDB serves as the primary structured data store for agent state, backtest results, strategy parameters, and market data.

#### Schema

```sql
-- alpha_search/agents/memory/schema.sql

-- Agent state snapshots
CREATE TABLE IF NOT EXISTS agent_state (
    id INTEGER PRIMARY KEY,
    agent_id VARCHAR NOT NULL,
    agent_type VARCHAR NOT NULL,
    state_json JSON NOT NULL,
    checkpoint_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id VARCHAR NOT NULL,
    parent_checkpoint INTEGER REFERENCES agent_state(id)
);

CREATE INDEX idx_agent_state_agent ON agent_state(agent_id, checkpoint_at);
CREATE INDEX idx_agent_state_session ON agent_state(session_id);

-- Task execution history
CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY,
    task_id VARCHAR NOT NULL UNIQUE,
    agent_id VARCHAR NOT NULL,
    task_type VARCHAR NOT NULL,
    input_json JSON,
    output_json JSON,
    status VARCHAR DEFAULT 'pending', -- pending, running, completed, failed, retrying
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    dependencies JSON, -- array of task_ids
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_task_agent ON task_history(agent_id, status);
CREATE INDEX idx_task_status ON task_history(status, created_at);

-- Strategy parameter history
CREATE TABLE IF NOT EXISTS strategy_runs (
    id INTEGER PRIMARY KEY,
    strategy_name VARCHAR NOT NULL,
    strategy_type VARCHAR NOT NULL,
    parameters_json JSON NOT NULL,
    backtest_config_json JSON NOT NULL,
    results_json JSON,
    metrics_json JSON,
    sharpe_ratio DOUBLE,
    max_drawdown DOUBLE,
    total_return DOUBLE,
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_id VARCHAR,
    session_id VARCHAR
);

CREATE INDEX idx_strategy_name ON strategy_runs(strategy_name, run_at);
CREATE INDEX idx_strategy_sharpe ON strategy_runs(sharpe_ratio);

-- Market data cache (with TTL)
CREATE TABLE IF NOT EXISTS market_data_cache (
    id INTEGER PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    source VARCHAR NOT NULL,
    timeframe VARCHAR NOT NULL,
    data_json JSON NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    row_count INTEGER
);

CREATE INDEX idx_market_data_lookup ON market_data_cache(symbol, source, timeframe, expires_at);

-- Portfolio snapshots
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id INTEGER PRIMARY KEY,
    portfolio_id VARCHAR NOT NULL,
    positions_json JSON NOT NULL,
    total_value DOUBLE NOT NULL,
    cash DOUBLE NOT NULL,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metrics_json JSON
);

CREATE INDEX idx_portfolio_lookup ON portfolio_snapshots(portfolio_id, snapshot_at);

-- Agent communication log
CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY,
    message_id VARCHAR NOT NULL UNIQUE,
    from_agent VARCHAR NOT NULL,
    to_agent VARCHAR NOT NULL,
    message_type VARCHAR NOT NULL, -- request, response, event, broadcast
    payload_json JSON NOT NULL,
    correlation_id VARCHAR, -- links request to response
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    received_at TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE INDEX idx_message_to ON agent_messages(to_agent, sent_at);
CREATE INDEX idx_message_correlation ON agent_messages(correlation_id);
```

#### Python Interface

```python
# alpha_search/agents/memory/duckdb_store.py
"""DuckDB-backed structured memory for agents."""

import json
import duckdb
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from contextlib import contextmanager


class DuckDBMemoryStore:
    """Persistent structured memory using DuckDB.

    All agent state, backtest results, and task history is stored
    in a local DuckDB database with ACID guarantees.
    """

    def __init__(self, db_path: str = "~/.alpha_search/agents/memory.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema from SQL file."""
        schema_path = Path(__file__).parent / "schema.sql"
        with self._connect() as conn:
            conn.execute(schema_path.read_text())

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = duckdb.connect(str(self.db_path))
        try:
            yield conn
        finally:
            conn.close()

    def save_agent_state(
        self,
        agent_id: str,
        agent_type: str,
        state: dict,
        session_id: str,
        parent_checkpoint: Optional[int] = None,
    ) -> int:
        """Save agent state snapshot. Returns checkpoint ID."""
        with self._connect() as conn:
            result = conn.execute(
                """
                INSERT INTO agent_state (agent_id, agent_type, state_json, session_id, parent_checkpoint)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
                """,
                [agent_id, agent_type, json.dumps(state), session_id, parent_checkpoint],
            )
            return result.fetchone()[0]

    def load_agent_state(self, agent_id: str, session_id: str) -> Optional[dict]:
        """Load the most recent state for an agent in a session."""
        with self._connect() as conn:
            result = conn.execute(
                """
                SELECT state_json, checkpoint_at
                FROM agent_state
                WHERE agent_id = ? AND session_id = ?
                ORDER BY checkpoint_at DESC
                LIMIT 1
                """,
                [agent_id, session_id],
            )
            row = result.fetchone()
            return json.loads(row[0]) if row else None

    def get_state_history(
        self,
        agent_id: str,
        session_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get state history for an agent, useful for debugging."""
        with self._connect() as conn:
            result = conn.execute(
                """
                SELECT id, checkpoint_at, state_json
                FROM agent_state
                WHERE agent_id = ? AND session_id = ?
                ORDER BY checkpoint_at DESC
                LIMIT ?
                """,
                [agent_id, session_id, limit],
            )
            return [
                {
                    "id": row[0],
                    "checkpoint_at": row[1],
                    "state": json.loads(row[2]),
                }
                for row in result.fetchall()
            ]

    def create_task(self, task: dict) -> str:
        """Create a new task. Returns task_id."""
        import uuid

        task_id = task.get("task_id", str(uuid.uuid4()))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO task_history
                (task_id, agent_id, task_type, input_json, dependencies, max_retries)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    task_id,
                    task["agent_id"],
                    task["task_type"],
                    json.dumps(task.get("input", {})),
                    json.dumps(task.get("dependencies", [])),
                    task.get("max_retries", 3),
                ],
            )
        return task_id

    def update_task_status(
        self,
        task_id: str,
        status: str,
        output: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update task status and optionally set output or error."""
        now = datetime.now().isoformat()
        with self._connect() as conn:
            if status == "running":
                conn.execute(
                    "UPDATE task_history SET status = ?, started_at = ? WHERE task_id = ?",
                    [status, now, task_id],
                )
            elif status in ("completed",):
                conn.execute(
                    "UPDATE task_history SET status = ?, output_json = ?, completed_at = ? WHERE task_id = ?",
                    [status, json.dumps(output) if output else None, now, task_id],
                )
            elif status == "failed":
                conn.execute(
                    """
                    UPDATE task_history
                    SET status = ?, error_message = ?, retry_count = retry_count + 1
                    WHERE task_id = ?
                    """,
                    [status, error, task_id],
                )

    def get_pending_tasks(self, agent_id: Optional[str] = None) -> list[dict]:
        """Get all pending tasks, optionally filtered by agent."""
        with self._connect() as conn:
            if agent_id:
                result = conn.execute(
                    """
                    SELECT task_id, agent_id, task_type, input_json, retry_count, max_retries
                    FROM task_history
                    WHERE agent_id = ? AND status IN ('pending', 'retrying')
                    ORDER BY created_at
                    """,
                    [agent_id],
                )
            else:
                result = conn.execute(
                    """
                    SELECT task_id, agent_id, task_type, input_json, retry_count, max_retries
                    FROM task_history
                    WHERE status IN ('pending', 'retrying')
                    ORDER BY created_at
                    """,
                )
            return [
                {
                    "task_id": row[0],
                    "agent_id": row[1],
                    "task_type": row[2],
                    "input": json.loads(row[3]),
                    "retry_count": row[4],
                    "max_retries": row[5],
                }
                for row in result.fetchall()
            ]

    def save_strategy_run(self, run_data: dict) -> int:
        """Save a strategy backtest run. Returns run ID."""
        with self._connect() as conn:
            result = conn.execute(
                """
                INSERT INTO strategy_runs
                (strategy_name, strategy_type, parameters_json, backtest_config_json,
                 results_json, metrics_json, sharpe_ratio, max_drawdown, total_return,
                 agent_id, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                [
                    run_data["strategy_name"],
                    run_data["strategy_type"],
                    json.dumps(run_data["parameters"]),
                    json.dumps(run_data["backtest_config"]),
                    json.dumps(run_data.get("results", {})),
                    json.dumps(run_data.get("metrics", {})),
                    run_data.get("sharpe_ratio"),
                    run_data.get("max_drawdown"),
                    run_data.get("total_return"),
                    run_data.get("agent_id"),
                    run_data.get("session_id"),
                ],
            )
            return result.fetchone()[0]

    def get_best_strategy_runs(
        self,
        strategy_name: str,
        metric: str = "sharpe_ratio",
        limit: int = 10,
    ) -> list[dict]:
        """Get top-performing strategy runs by metric."""
        with self._connect() as conn:
            result = conn.execute(
                f"""
                SELECT id, strategy_name, parameters_json, {metric}, run_at
                FROM strategy_runs
                WHERE strategy_name = ?
                ORDER BY {metric} DESC NULLS LAST
                LIMIT ?
                """,
                [strategy_name, limit],
            )
            return [
                {
                    "id": row[0],
                    "strategy": row[1],
                    "parameters": json.loads(row[2]),
                    metric: row[3],
                    "run_at": row[4],
                }
                for row in result.fetchall()
            ]
```

### 2. Markdown Journals -- Agent Logs

Each agent maintains a human-readable markdown journal for logging decisions, reasoning, errors, and observations.

#### Journal Format

```markdown
<!-- ~/.alpha_search/agents/journals/research-agent-2024-01.md -->

# Research Agent Journal -- January 2024

## Session: 2024-01-15T09:30:00Z

### 09:30 -- Task Started: Literature Review
- **Objective:** Review recent momentum strategy papers (2023--2024)
- **Input:** Query: "momentum anomaly recent papers"
- **Sources searched:** SSRN, JFE, RFS, AER

### 09:32 -- Finding: Asness et al. (2023)
- **Paper:** "Momentum in International Markets"
- **Key insight:** Momentum works better in emerging markets with higher limits-to-arbitrage
- **Relevance:** High -- supports expanding momentum to Indian NSE mid-caps
- **Action:** Flagged for Strategy Agent

### 09:45 -- Decision: Prioritize Emerging Market Momentum
- **Rationale:** Three recent papers confirm the effect
- **Risk:** Data quality concerns for NSE historical data pre-2010
- **Next step:** Request Market Data Agent to validate data coverage

### 09:50 -- Task Completed
- **Duration:** 20 minutes
- **Output:** 5 papers reviewed, 2 flagged for implementation
- **Correlation ID:** task-uuid-123
```

#### Python Interface

```python
# alpha_search/agents/memory/journal.py
"""Markdown journal logging for agent activities."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional


class AgentJournal:
    """Human-readable markdown journal for agent activities.

    Each agent maintains a monthly journal file with structured entries
    for decisions, observations, errors, and task completions.
    """

    JOURNAL_DIR = Path("~/.alpha_search/agents/journals").expanduser()

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

    def _get_journal_path(self) -> Path:
        """Get the current month's journal file path."""
        now = datetime.now()
        filename = f"{self.agent_id}-{now.year}-{now.month:02d}.md"
        return self.JOURNAL_DIR / filename

    def _ensure_header(self, path: Path) -> None:
        """Ensure journal file has a header."""
        if not path.exists():
            now = datetime.now()
            path.write_text(
                f"# {self.agent_id.replace('-', ' ').title()} Journal -- "
                f"{now.strftime('%B %Y')}\n\n"
            )

    def log_decision(self, decision: str, rationale: str, context: Optional[dict] = None) -> None:
        """Log a decision with rationale."""
        path = self._get_journal_path()
        self._ensure_header(path)

        timestamp = datetime.now().strftime("%H:%M")
        entry = f"\n### {timestamp} -- Decision: {decision}\n- **Rationale:** {rationale}\n"
        if context:
            entry += f"- **Context:** {context}\n"

        with open(path, "a") as f:
            f.write(entry)

    def log_observation(self, observation: str, source: Optional[str] = None) -> None:
        """Log an observation or finding."""
        path = self._get_journal_path()
        self._ensure_header(path)

        timestamp = datetime.now().strftime("%H:%M")
        entry = f"\n### {timestamp} -- Observation\n- {observation}\n"
        if source:
            entry += f"- **Source:** {source}\n"

        with open(path, "a") as f:
            f.write(entry)

    def log_error(self, error: str, context: Optional[dict] = None) -> None:
        """Log an error with context."""
        path = self._get_journal_path()
        self._ensure_header(path)

        timestamp = datetime.now().strftime("%H:%M")
        entry = f"\n### {timestamp} -- ERROR\n- **Error:** {error}\n"
        if context:
            entry += f"- **Context:** {context}\n"

        with open(path, "a") as f:
            f.write(entry)

    def log_task(self, task_id: str, task_type: str, status: str, details: Optional[str] = None) -> None:
        """Log task lifecycle events."""
        path = self._get_journal_path()
        self._ensure_header(path)

        timestamp = datetime.now().strftime("%H:%M")
        entry = f"\n### {timestamp} -- Task {status}: {task_type}\n- **Task ID:** {task_id}\n"
        if details:
            entry += f"- **Details:** {details}\n"

        with open(path, "a") as f:
            f.write(entry)

    def log(self, level: str, message: str, **kwargs) -> None:
        """Generic log entry."""
        path = self._get_journal_path()
        self._ensure_header(path)

        timestamp = datetime.now().strftime("%H:%M")
        entry = f"\n### {timestamp} -- {level.upper()}\n- {message}\n"
        for key, value in kwargs.items():
            entry += f"- **{key}:** {value}\n"

        with open(path, "a") as f:
            f.write(entry)
```

### 3. ChromaDB -- Vector Memory (Optional)

ChromaDB stores document embeddings for semantic search across research papers, strategy descriptions, and market data documentation.

#### Use Cases

| Use Case | Description |
|---|---|
| **Paper search** | Find relevant research papers by semantic similarity to a query |
| **Strategy matching** | Match a research idea to existing strategy implementations |
| **Error diagnosis** | Search past error logs for similar issues and resolutions |
| **Knowledge retrieval** | Query accumulated agent knowledge with natural language |

#### Configuration

```python
# alpha_search/agents/memory/vector_store.py
"""ChromaDB vector memory for semantic search."""

import os
from typing import Optional
from pathlib import Path


class VectorMemoryStore:
    """Optional vector memory using ChromaDB.

    Enabled only when chromadb package is installed and
    QUANT_OS_VECTOR_MEMORY_ENABLED is set to true.
    """

    def __init__(self, persist_dir: str = "~/.alpha_search/agents/vector_db"):
        self.persist_dir = Path(persist_dir).expanduser()
        self._client = None
        self._collections = {}

        self.enabled = os.environ.get("QUANT_OS_VECTOR_MEMORY_ENABLED", "false").lower() == "true"
        if self.enabled:
            try:
                import chromadb
                self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            except ImportError:
                self.enabled = False

    def _get_collection(self, name: str):
        """Get or create a collection."""
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(name)
        return self._collections[name]

    def add_documents(
        self,
        collection: str,
        documents: list[str],
        ids: list[str],
        metadatas: Optional[list[dict]] = None,
    ) -> None:
        """Add documents to vector memory."""
        if not self.enabled:
            return

        coll = self._get_collection(collection)
        coll.add(documents=documents, ids=ids, metadatas=metadatas)

    def search(
        self,
        collection: str,
        query: str,
        n_results: int = 5,
        filter_dict: Optional[dict] = None,
    ) -> list[dict]:
        """Search vector memory by semantic similarity."""
        if not self.enabled:
            return []

        coll = self._get_collection(collection)
        results = coll.query(
            query_texts=[query],
            n_results=n_results,
            where=filter_dict,
        )

        return [
            {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            }
            for i in range(len(results["ids"][0]))
        ]

    def delete_collection(self, name: str) -> None:
        """Delete a collection."""
        if not self.enabled:
            return
        self._client.delete_collection(name)
        self._collections.pop(name, None)
```

---

## Task Orchestration

### Task Flow

```
+------------+     +-----------+     +-----------+     +-----------+
|  Submit    | --> |  Queue    | --> |  Assign   | --> |  Execute  |
|  Task      |     |  (Redis)  |     |  Agent    |     |  Task     |
+------------+     +-----------+     +-----------+     +-----+-----+
                                                           |
                     +-------------------------------------+
                     |
              +------v------+     +-----------+     +-----------+
              |  Success    | --> |  Save     | --> |  Notify   |
              |             |     |  Results  |     |  Next     |
              +-------------+     +-----------+     +-----------+

              +------v------+     +-----------+     +-----------+
              |  Failure    | --> |  Retry?   | --> |  Save     |
              |             |     | (max 3)   |     |  Error    |
              +-------------+     +-----------+     +-----------+
```

### Implementation

```python
# alpha_search/agents/orchestrator.py
"""Task orchestration for multi-agent workflows."""

import json
import redis
import logging
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass, asdict

from alpha_search.agents.memory.duckdb_store import DuckDBMemoryStore
from alpha_search.agents.memory.journal import AgentJournal

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """Represents a unit of work in the agent system."""

    task_id: str
    task_type: str
    agent_id: str
    input_data: dict
    status: str = "pending"  # pending, running, completed, failed, retrying
    output_data: Optional[dict] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: list[str] = None
    created_at: str = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    priority: int = 5  # 1 = highest, 10 = lowest

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class TaskOrchestrator:
    """Central task orchestrator using Redis Streams and DuckDB."""

    TASK_STREAM = "alpha_search:tasks"
    RESULT_STREAM = "alpha_search:results"
    AGENT_CHANNEL_PREFIX = "alpha_search:agent:"

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        db_path: str = "~/.alpha_search/agents/memory.db",
    ):
        self.redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True,
        )
        self.db = DuckDBMemoryStore(db_path)
        self.journals = {}  # agent_id -> AgentJournal
        self._running = False

    def _get_journal(self, agent_id: str) -> AgentJournal:
        """Get or create journal for an agent."""
        if agent_id not in self.journals:
            self.journals[agent_id] = AgentJournal(agent_id)
        return self.journals[agent_id]

    def submit_task(self, task: Task) -> str:
        """Submit a task to the queue. Returns task_id."""
        # Persist to DuckDB
        self.db.create_task(task.to_dict())

        # Publish to Redis Stream
        self.redis.xadd(
            self.TASK_STREAM,
            {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "agent_id": task.agent_id,
                "input": json.dumps(task.input_data),
                "priority": task.priority,
                "dependencies": json.dumps(task.dependencies),
            },
        )

        # Log to journal
        journal = self._get_journal(task.agent_id)
        journal.log_task(task.task_id, task.task_type, "Submitted")

        logger.info(f"Task {task.task_id} submitted for agent {task.agent_id}")
        return task.task_id

    def get_next_task(self, agent_id: str) -> Optional[Task]:
        """Get the next pending task for an agent, respecting dependencies."""
        pending = self.db.get_pending_tasks(agent_id)

        for task_data in pending:
            # Check dependencies
            deps = task_data.get("dependencies", [])
            if deps:
                # Verify all dependencies are completed
                with self.db._connect() as conn:
                    placeholders = ",".join("?" * len(deps))
                    result = conn.execute(
                        f"SELECT task_id, status FROM task_history WHERE task_id IN ({placeholders})",
                        deps,
                    )
                    dep_statuses = {row[0]: row[1] for row in result.fetchall()}

                if not all(s == "completed" for s in dep_statuses.values()):
                    continue  # Dependencies not met yet

            return Task(
                task_id=task_data["task_id"],
                task_type=task_data["task_type"],
                agent_id=task_data["agent_id"],
                input_data=task_data["input"],
                retry_count=task_data["retry_count"],
                max_retries=task_data["max_retries"],
            )

        return None

    def complete_task(self, task_id: str, output: dict) -> None:
        """Mark a task as completed with output."""
        self.db.update_task_status(task_id, "completed", output=output)

        # Publish result
        self.redis.xadd(
            self.RESULT_STREAM,
            {
                "task_id": task_id,
                "status": "completed",
                "output": json.dumps(output),
                "completed_at": datetime.now().isoformat(),
            },
        )

        logger.info(f"Task {task_id} completed")

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark a task as failed with error."""
        task_data = self.db._get_task(task_id)
        if task_data and task_data["retry_count"] < task_data["max_retries"]:
            self.db.update_task_status(task_id, "retrying", error=error)
            # Re-queue the task
            self.redis.xadd(
                self.TASK_STREAM,
                {
                    "task_id": task_id,
                    "task_type": task_data["task_type"],
                    "agent_id": task_data["agent_id"],
                    "input": task_data["input_json"],
                    "retry": "true",
                },
            )
            logger.warning(f"Task {task_id} failed, retrying ({task_data['retry_count'] + 1}/{task_data['max_retries']})")
        else:
            self.db.update_task_status(task_id, "failed", error=error)
            logger.error(f"Task {task_id} failed permanently: {error}")

    def broadcast_event(self, event_type: str, payload: dict) -> None:
        """Broadcast an event to all agents."""
        self.redis.publish(
            "alpha_search:events",
            json.dumps({
                "type": event_type,
                "payload": payload,
                "timestamp": datetime.now().isoformat(),
            }),
        )

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get current status of a task."""
        with self.db._connect() as conn:
            result = conn.execute(
                """
                SELECT task_id, agent_id, task_type, status,
                       started_at, completed_at, error_message, retry_count
                FROM task_history
                WHERE task_id = ?
                """,
                [task_id],
            )
            row = result.fetchone()
            if row:
                return {
                    "task_id": row[0],
                    "agent_id": row[1],
                    "task_type": row[2],
                    "status": row[3],
                    "started_at": row[4],
                    "completed_at": row[5],
                    "error": row[6],
                    "retry_count": row[7],
                }
            return None

    def get_system_status(self) -> dict:
        """Get overall system status for monitoring."""
        with self.db._connect() as conn:
            pending = conn.execute("SELECT COUNT(*) FROM task_history WHERE status IN ('pending', 'retrying')").fetchone()[0]
            running = conn.execute("SELECT COUNT(*) FROM task_history WHERE status = 'running'").fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM task_history WHERE status = 'completed'").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM task_history WHERE status = 'failed'").fetchone()[0]

        return {
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "timestamp": datetime.now().isoformat(),
        }
```

---

## Inter-Agent Communication

### Communication Patterns

```
Pattern 1: Request-Response
+----------------+    request     +----------------+
| Research Agent | --------------> | Market Agent   |
|                | <-------------- |                |
+----------------+    response    +----------------+

Pattern 2: Publish-Subscribe (Events)
+----------------+    event       +----------------+
| Market Agent   | --------------> | All Agents     |
| (data updated) |                | (subscribed)   |
+----------------+                +----------------+

Pattern 3: Pipeline
+----------------+    output      +----------------+    output      +----------------+
| Data Agent     | -------------> | Strategy Agent | -------------> | Backtest Agent |
| (fetch data)   |                | (generate      |                | (run backtest) |
+----------------+                |  signals)      |                +----------------+
                                  +----------------+

Pattern 4: Fan-Out / Fan-In
                    +----------------+
         +--------->| Risk Agent     |
         |          | (assess risk)  |
         |          +----------------+
         |
+----------------+   +----------------+
| Portfolio      |-->| Strategy Agent |
| (rebalance     |   | (optimize)     |
|  signal)       |   +----------------+
|                |
|                |   +----------------+
|                +-->| Reporting Agent|
|                    | (generate      |
|                    |  report)       |
+----------------+   +----------------+
```

### Message Format

```python
# alpha_search/agents/messaging.py
"""Inter-agent messaging protocol."""

import json
import uuid
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Any
from enum import Enum


class MessageType(Enum):
    """Types of inter-agent messages."""

    REQUEST = "request"         # Ask another agent to do something
    RESPONSE = "response"       # Reply to a request
    EVENT = "event"             # Broadcast that something happened
    HEARTBEAT = "heartbeat"     # Health check
    ERROR = "error"             # Error notification
    COMMAND = "command"         # Direct instruction from orchestrator


class MessagePriority(Enum):
    """Message priority levels."""

    CRITICAL = 1    # System-critical, process immediately
    HIGH = 2        # Important task-related
    NORMAL = 3      # Standard communication
    LOW = 4         # Background tasks
    BATCH = 5       # Can be deferred


@dataclass
class AgentMessage:
    """Standard message format for inter-agent communication."""

    message_id: str
    message_type: str
    from_agent: str
    to_agent: str  # "broadcast" for events
    payload: dict
    correlation_id: Optional[str] = None  # Links request to response
    priority: int = 3  # NORMAL
    timestamp: str = None
    ttl_seconds: Optional[int] = None  # Message expires after TTL

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "AgentMessage":
        return cls(**json.loads(data))

    @classmethod
    def request(
        cls,
        from_agent: str,
        to_agent: str,
        action: str,
        params: dict,
        priority: int = 3,
    ) -> "AgentMessage":
        """Create a request message."""
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.REQUEST.value,
            from_agent=from_agent,
            to_agent=to_agent,
            payload={"action": action, "params": params},
            priority=priority,
        )

    @classmethod
    def response(
        cls,
        from_agent: str,
        to_agent: str,
        request_id: str,
        result: dict,
        success: bool = True,
    ) -> "AgentMessage":
        """Create a response message."""
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.RESPONSE.value,
            from_agent=from_agent,
            to_agent=to_agent,
            payload={"result": result, "success": success},
            correlation_id=request_id,
        )

    @classmethod
    def event(
        cls,
        from_agent: str,
        event_type: str,
        data: dict,
    ) -> "AgentMessage":
        """Create an event broadcast message."""
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=MessageType.EVENT.value,
            from_agent=from_agent,
            to_agent="broadcast",
            payload={"event_type": event_type, "data": data},
        )
```

---

## Agent Lifecycle

### State Machine

```
                    +---------+
                    | CREATED |
                    +----+----+
                         |
                         | register()
                         v
+--------+    error   +---------+   initialize()   +------------+
| FAILED | <---------+ PENDING +----------------->+ INITIALIZING|
+--------+           +----+----+                  +-----+------+
                          |                             |
                          | timeout                     | init complete
                          v                             v
                   +---------+                   +------------+
                   | TIMEOUT |                   |   READY    |
                   +---------+                   +-----+------+
                                                       |
                              +------------------------+------------+
                              |                        |            |
                              | task assigned          | idle       | shutdown
                              v                        v            v
                         +---------+             +---------+   +---------+
                         | RUNNING |             |  IDLE   |   |STOPPING |
                         +----+----+             +----+----+   +----+----+
                              |                        |            |
               +--------------+-----------+            |            |
               |              |           |            |            |
               v              v           v            |            |
          +---------+    +---------+  +---------+      |            |
          |COMPLETED|    |  ERROR  |  |TIMEOUT  |      |            |
          +----+----+    +----+----+  +----+----+      |            |
               |              |           |            |            |
               |              +-----+-----+            |            |
               |                    |                  |            |
               +--------------------+                  |            |
                                    |                  |            |
                                    v                  v            v
                              +---------+        +---------+   +---------+
                              | PENDING |        |  IDLE   |   | STOPPED |
                              | (retry) |        +---------+   +---------+
                              +---------+
```

### Base Agent Implementation

```python
# alpha_search/agents/agent.py
"""Base agent class with lifecycle management."""

import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Optional

from alpha_search.agents.memory.duckdb_store import DuckDBMemoryStore
from alpha_search.agents.memory.journal import AgentJournal
from alpha_search.agents.messaging import AgentMessage, MessageType

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent lifecycle states."""

    CREATED = "created"
    PENDING = "pending"
    INITIALIZING = "initializing"
    READY = "ready"
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"
    STOPPING = "stopping"
    STOPPED = "stopped"


class BaseAgent(ABC):
    """Base class for all Alpha Search agents.

    All agents inherit from this class and implement:
    - `initialize()`: One-time setup
    - `execute_task(task_input)`: Main task handler
    - `shutdown()`: Cleanup

    Agents automatically manage:
    - State persistence (DuckDB)
    - Logging (Markdown journal)
    - Health reporting
    """

    def __init__(
        self,
        agent_type: str,
        agent_id: Optional[str] = None,
        db_path: str = "~/.alpha_search/agents/memory.db",
    ):
        self.agent_id = agent_id or f"{agent_type}-{uuid.uuid4().hex[:8]}"
        self.agent_type = agent_type
        self.state = AgentState.CREATED
        self.session_id = str(uuid.uuid4())
        self.current_task: Optional[str] = None

        # Memory subsystems
        self.db = DuckDBMemoryStore(db_path)
        self.journal = AgentJournal(self.agent_id)

        # Internal state
        self._initialized = False
        self._task_count = 0
        self._error_count = 0

        logger.info(f"Agent {self.agent_id} ({agent_type}) created")

    def initialize(self) -> None:
        """Initialize the agent. Override for custom setup."""
        self.state = AgentState.INITIALIZING
        self._save_state()

        try:
            self._initialize()
            self._initialized = True
            self.state = AgentState.READY
            self.journal.log("INFO", f"Agent {self.agent_id} initialized successfully")
        except Exception as e:
            self.state = AgentState.ERROR
            self.journal.log_error(f"Initialization failed: {e}")
            raise

        self._save_state()
        logger.info(f"Agent {self.agent_id} initialized")

    def execute(self, task_input: dict) -> dict:
        """Execute a task. This is the main entry point."""
        if not self._initialized:
            raise RuntimeError("Agent must be initialized before executing tasks")

        self.state = AgentState.RUNNING
        self._task_count += 1
        self._save_state()

        try:
            self.journal.log(
                "INFO",
                f"Starting task execution",
                task_input=str(task_input)[:200],
            )

            result = self._execute(task_input)

            self.state = AgentState.COMPLETED
            self.journal.log(
                "INFO",
                f"Task completed successfully",
                result_summary=str(result)[:200],
            )

            return result

        except Exception as e:
            self._error_count += 1
            self.state = AgentState.ERROR
            self.journal.log_error(f"Task execution failed: {e}", context={"input": task_input})
            raise

        finally:
            self._save_state()

    def shutdown(self) -> None:
        """Shutdown the agent gracefully."""
        self.state = AgentState.STOPPING
        self._save_state()

        try:
            self._shutdown()
            self.state = AgentState.STOPPED
            self.journal.log("INFO", f"Agent {self.agent_id} shutdown complete")
        except Exception as e:
            self.state = AgentState.ERROR
            self.journal.log_error(f"Shutdown error: {e}")

        self._save_state()
        logger.info(f"Agent {self.agent_id} stopped")

    def _save_state(self) -> None:
        """Persist current state to DuckDB."""
        state_data = {
            "state": self.state.value,
            "session_id": self.session_id,
            "task_count": self._task_count,
            "error_count": self._error_count,
            "current_task": self.current_task,
            "last_updated": datetime.now().isoformat(),
        }
        self.db.save_agent_state(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            state=state_data,
            session_id=self.session_id,
        )

    @abstractmethod
    def _initialize(self) -> None:
        """Override: one-time initialization logic."""
        pass

    @abstractmethod
    def _execute(self, task_input: dict) -> dict:
        """Override: main task execution logic."""
        pass

    @abstractmethod
    def _shutdown(self) -> None:
        """Override: cleanup logic."""
        pass

    def get_stats(self) -> dict:
        """Get agent statistics."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "state": self.state.value,
            "session_id": self.session_id,
            "tasks_executed": self._task_count,
            "errors": self._error_count,
            "success_rate": (self._task_count - self._error_count) / max(self._task_count, 1),
        }
```

---

## Deployment Configuration

### Docker Compose (Full Stack)

```yaml
# docker-compose.agents.yml
version: "3.8"

services:
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"
    networks:
      - agent-net
    restart: unless-stopped

  alpha-search-agents:
    build:
      context: .
      dockerfile: Dockerfile
    environment:
      - QUANT_OS_ENV=production
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - QUANT_OS_VECTOR_MEMORY_ENABLED=true
    volumes:
      - agent-data:/app/.alpha_search/agents
    depends_on:
      - redis
    networks:
      - agent-net
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 512M

  # Optional: ChromaDB for vector memory
  chromadb:
    image: chromadb/chroma:latest
    volumes:
      - chroma-data:/chroma/chroma
    ports:
      - "8000:8000"
    environment:
      - CHROMA_SERVER_AUTHN_PROVIDER=chromadb.auth.token_authn.TokenAuthenticationServerProvider
      - CHROMA_SERVER_AUTHN_CREDENTIALS=${CHROMA_AUTH_TOKEN}
    networks:
      - agent-net
    restart: unless-stopped
    profiles:
      - vector-memory

volumes:
  redis-data:
  agent-data:
  chroma-data:

networks:
  agent-net:
    driver: bridge
```

### Environment Variables

```bash
# Agent system configuration
QUANT_OS_ENV=development
AGENT_WORKERS=4                    # Number of concurrent agent workers
AGENT_TASK_TIMEOUT=300             # Task timeout in seconds
AGENT_HEARTBEAT_INTERVAL=30        # Health check interval in seconds

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0

# Vector memory (optional)
QUANT_OS_VECTOR_MEMORY_ENABLED=false
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_AUTH_TOKEN=your_auth_token

# Persistence
AGENT_DB_PATH=~/.alpha_search/agents/memory.db
AGENT_JOURNAL_DIR=~/.alpha_search/agents/journals
AGENT_VECTOR_DB_PATH=~/.alpha_search/agents/vector_db
```

---

## Monitoring

### Health Checks

```python
# alpha_search/agents/monitoring.py
"""Monitoring and observability for the agent system."""

import json
import time
from datetime import datetime
from typing import Optional

import redis

from alpha_search.agents.memory.duckdb_store import DuckDBMemoryStore


class AgentMonitor:
    """Health monitoring and metrics collection for agents."""

    def __init__(
        self,
        redis_client: redis.Redis,
        db: DuckDBMemoryStore,
    ):
        self.redis = redis_client
        self.db = db

    def get_health(self) -> dict:
        """Get overall system health."""
        # Check Redis connectivity
        redis_healthy = False
        redis_latency_ms = None
        try:
            start = time.time()
            self.redis.ping()
            redis_latency_ms = (time.time() - start) * 1000
            redis_healthy = True
        except Exception:
            pass

        # Check database
        db_healthy = False
        try:
            with self.db._connect() as conn:
                conn.execute("SELECT 1")
                db_healthy = True
        except Exception:
            pass

        # Task statistics
        status = self.db.get_system_status()

        return {
            "status": "healthy" if (redis_healthy and db_healthy) else "degraded",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "redis": {
                    "healthy": redis_healthy,
                    "latency_ms": round(redis_latency_ms, 2) if redis_latency_ms else None,
                },
                "database": {"healthy": db_healthy},
            },
            "tasks": status,
        }

    def get_agent_health(self, agent_id: str) -> Optional[dict]:
        """Get health status for a specific agent."""
        state = self.db.load_agent_state(agent_id, session_id="*")
        if not state:
            return None

        return {
            "agent_id": agent_id,
            "state": state.get("state", "unknown"),
            "task_count": state.get("task_count", 0),
            "error_count": state.get("error_count", 0),
            "last_updated": state.get("last_updated"),
        }

    def export_metrics(self) -> dict:
        """Export metrics for external monitoring (Prometheus, etc.)."""
        status = self.db.get_system_status()

        return {
            "alpha_search_agent_tasks_pending": status["pending"],
            "alpha_search_agent_tasks_running": status["running"],
            "alpha_search_agent_tasks_completed_total": status["completed"],
            "alpha_search_agent_tasks_failed_total": status["failed"],
            "alpha_search_agent_up": 1 if self.get_health()["status"] == "healthy" else 0,
        }
```

### Log Aggregation

Agent journals are written as markdown files and can be:

1. **Viewed directly:** `cat ~/.alpha_search/agents/journals/research-agent-2024-01.md`
2. **Searched:** `grep "ERROR" ~/.alpha_search/agents/journals/*.md`
3. **Tailed in real-time:** `tail -f ~/.alpha_search/agents/journals/*.md`
4. **Shipped to external systems:** Configure `journald`, `fluentd`, or `filebeat`

---

*This document is version-controlled. Last updated: v0.1.0*
