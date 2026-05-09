# Alpha Search Memory Directory

This directory contains the **human-readable memory layer** for the Alpha Search project.
Every entry is dual-written: once to the structured DuckDB database and once to
these Markdown files. The Markdown files exist so humans (and LLMs reading plain
text) can understand project history without querying a database.

## Directory Structure

```
memory/
├── README.md                   <- You are here
├── quantos_memory.db           <- DuckDB (or SQLite) structured database
├── agent_journal.md            <- Task log, blockers, handoffs
├── architecture_decisions.md   <- Key architecture & design decisions
├── strategy_findings.md        <- Strategy evaluation results
├── risk_log.md                 <- Risk decisions & flags
├── project_memory.md           <- Project-level summary & direction
└── blockers.md                 <- Standalone blocker tracking
```

## File Reference

| File | Content | Written By |
|------|---------|------------|
| `agent_journal.md` | Tasks completed, blockers raised, agent handoffs | `AgentJournal.log_task()`, `.log_blocker()`, `.log_handoff()` |
| `architecture_decisions.md` | Architecture & design decisions with rationale | `AgentJournal.log_decision()` |
| `strategy_findings.md` | Strategy backtest results and verdicts | `AgentJournal.log_strategy_result()` |
| `risk_log.md` | Risk decisions (approve/block/flag/defer) | `AgentJournal.log_risk_decision()` |
| `project_memory.md` | High-level project direction and positioning | Seeded manually, updated by project coordinator |

## Reading These Files

Each entry follows a consistent format:

```markdown
### [YYYY-MM-DD HH:MM:SS UTC] AgentName — Title (status)

Details...

Tags: tag1, tag2
---
```

- **Timestamps** are always UTC.
- **Severity indicators**: 🔴 high / 🟡 medium / 🟢 low
- **Verdict badges**: ✅ accepted / ❌ rejected / 👀 watch / 🧪 needs testing
- **Decision badges**: ✅ approve / 🚫 block / 🚩 flag / ⏳ defer

## Programmatic Access

Use the Python API for structured queries:

```python
from alpha_search.memory import MemoryStore, MemoryRetriever

store = MemoryStore("memory/quantos_memory.db")
retriever = MemoryRetriever(store)

# Get context for a specific agent
context = retriever.build_agent_prompt_context("architect")
print(context)
```

## Seeding

Initial entries in these Markdown files were seeded from project history to
give the agent swarm a starting context. New entries are appended automatically
as agents run.
