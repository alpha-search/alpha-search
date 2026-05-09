-- Quant.OS Memory Schema v1
-- Works with both DuckDB and SQLite.

-- ---------------------------------------------------------------------------
-- Table: agent_memory
-- General-purpose memory records created by agents.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_memory (
    id               TEXT PRIMARY KEY,
    agent_name       TEXT NOT NULL,
    memory_type      TEXT NOT NULL,
    title            TEXT NOT NULL,
    content          TEXT NOT NULL DEFAULT '',
    tags             TEXT NOT NULL DEFAULT '[]',
    importance_score REAL NOT NULL DEFAULT 0.5,
    status           TEXT NOT NULL DEFAULT 'active',
    source_file      TEXT,
    related_task     TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_agent_name
    ON agent_memory (agent_name);

CREATE INDEX IF NOT EXISTS idx_agent_memory_memory_type
    ON agent_memory (memory_type);

CREATE INDEX IF NOT EXISTS idx_agent_memory_status
    ON agent_memory (status);

CREATE INDEX IF NOT EXISTS idx_agent_memory_importance_score
    ON agent_memory (importance_score DESC);

CREATE INDEX IF NOT EXISTS idx_agent_memory_created_at
    ON agent_memory (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_memory_related_task
    ON agent_memory (related_task);

CREATE INDEX IF NOT EXISTS idx_agent_memory_agent_type_status
    ON agent_memory (agent_name, memory_type, status);

-- ---------------------------------------------------------------------------
-- Table: strategy_memory
-- Results of strategy evaluations / backtests.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS strategy_memory (
    id                           TEXT PRIMARY KEY,
    strategy_name                TEXT NOT NULL,
    strategy_type                TEXT NOT NULL,
    market                       TEXT NOT NULL DEFAULT 'global',
    asset_class                  TEXT NOT NULL DEFAULT 'equity',
    universe                     TEXT NOT NULL DEFAULT '[]',
    hypothesis                   TEXT NOT NULL,
    result_summary               TEXT NOT NULL DEFAULT '',
    sharpe                       REAL,
    max_drawdown                 REAL,
    total_return                 REAL,
    win_rate                     REAL,
    turnover                     REAL,
    transaction_cost_assumption  TEXT,
    validation_method            TEXT NOT NULL DEFAULT '',
    verdict                      TEXT NOT NULL DEFAULT 'watch',
    rejection_reason             TEXT,
    lessons_learned              TEXT NOT NULL DEFAULT '',
    created_at                   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_strategy_memory_strategy_name
    ON strategy_memory (strategy_name);

CREATE INDEX IF NOT EXISTS idx_strategy_memory_strategy_type
    ON strategy_memory (strategy_type);

CREATE INDEX IF NOT EXISTS idx_strategy_memory_market
    ON strategy_memory (market);

CREATE INDEX IF NOT EXISTS idx_strategy_memory_asset_class
    ON strategy_memory (asset_class);

CREATE INDEX IF NOT EXISTS idx_strategy_memory_verdict
    ON strategy_memory (verdict);

CREATE INDEX IF NOT EXISTS idx_strategy_memory_sharpe
    ON strategy_memory (sharpe DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_memory_created_at
    ON strategy_memory (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategy_memory_type_verdict
    ON strategy_memory (strategy_type, verdict);

-- ---------------------------------------------------------------------------
-- Table: handoffs
-- Inter-agent task handoffs.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS handoffs (
    id          TEXT PRIMARY KEY,
    from_agent  TEXT NOT NULL,
    to_agent    TEXT NOT NULL,
    task        TEXT NOT NULL,
    context     TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_handoffs_from_agent
    ON handoffs (from_agent);

CREATE INDEX IF NOT EXISTS idx_handoffs_to_agent
    ON handoffs (to_agent);

CREATE INDEX IF NOT EXISTS idx_handoffs_status
    ON handoffs (status);

CREATE INDEX IF NOT EXISTS idx_handoffs_created_at
    ON handoffs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_handoffs_to_status
    ON handoffs (to_agent, status);

-- ---------------------------------------------------------------------------
-- Table: risk_decisions
-- Risk-management decisions and check results.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS risk_decisions (
    id          TEXT PRIMARY KEY,
    agent_name  TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id   TEXT NOT NULL,
    decision    TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    severity    TEXT NOT NULL DEFAULT 'medium',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_risk_decisions_agent_name
    ON risk_decisions (agent_name);

CREATE INDEX IF NOT EXISTS idx_risk_decisions_object_type
    ON risk_decisions (object_type);

CREATE INDEX IF NOT EXISTS idx_risk_decisions_decision
    ON risk_decisions (decision);

CREATE INDEX IF NOT EXISTS idx_risk_decisions_severity
    ON risk_decisions (severity);

CREATE INDEX IF NOT EXISTS idx_risk_decisions_created_at
    ON risk_decisions (created_at DESC);
