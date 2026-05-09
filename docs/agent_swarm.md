# Agent Swarm Architecture

Alpha Search is developed by a decentralised swarm of nine specialised agents. Each agent owns a distinct domain, communicates through well-defined interfaces, and operates autonomously within its scope.

---

## Agent Diagram

```
+-----------------------------------------------------------------+
|                        Coordinator Agent                         |
|              (routing, scheduling, conflict resolution)         |
+----------+-------------+-------------+-------------+------------+
           |             |             |             |
+----------v--+  +-------v-----+  +----v--------+  +--v----------+
|  Data Agent |  |  Signals    |  |  Backtest   |  |  Sentiment  |
|  (provider  |  |  Agent      |  |  Agent      |  |  Agent      |
|   registry, |  |  (primitive |  |  (engine,   |  |  (FinBERT,  |
|   cache,    |  |   library)  |  |   metrics)  |  |   composite)|
+-------------+  +-------------+  +-------------+  +-------------+
+----------+--+  +-------------+  +-------------+
|  Walk-   |     |  Portfolio  |  |  Terminal   |
|  Forward |     |  Optimizer  |  |  Agent      |
|  Agent   |     |  Agent      |  |  (UI, CLI,  |
|          |     |  (MVO,RP,   |  |   API)      |
|          |     |   HRP)      |  |             |
+----------+     +-------------+  +-------------+
+----------+
|  Global  |
| Market   |
| Opport-  |
| unity    |
| Agent    |
+----------+
```

---

## Agent Descriptions

### 1. Coordinator Agent

**Role:** Orchestration and cross-cutting concerns  
**Responsibilities:**
- Route tasks to the correct specialised agent
- Detect and resolve conflicts between agent outputs
- Enforce project-wide standards (style, types, tests)
- Maintain the build pipeline and CI/CD configuration

**Interface:**
```python
coordinator.dispatch(task: Task) -> Result
coordinator.resolve_conflict(a: Result, b: Result) -> Result
```

---

### 2. Data Agent

**Role:** All data ingestion and caching  
**Responsibilities:**
- Maintain the provider registry (Yahoo Finance, Binance, extensible)
- Implement the DuckDB cache manager with TTL
- Normalise OHLCV schemas across providers
- Handle rate-limiting, retries, and authentication

**Key module:** `alpha_search.data_providers`, `alpha_search.cache`

---

### 3. Signals Agent

**Role:** Signal generation primitives  
**Responsibilities:**
- Implement vectorised signal functions (momentum, MA cross, z-score, etc.)
- Design the ensemble and composition API
- Ensure all signals are pure functions (no side effects)
- Optimise hot paths with Numba where beneficial

**Key module:** `alpha_search.signals`

---

### 4. Backtest Agent

**Role:** Strategy simulation and performance measurement  
**Responsibilities:**
- Maintain the vectorised backtest engine
- Implement transaction-cost and slippage models
- Compute metrics: Sharpe, Sortino, Calmar, max drawdown, win rate
- Generate equity curves, trade logs, and position histories

**Key module:** `alpha_search.backtest`

---

### 5. Sentiment Agent

**Role:** NLP-based financial sentiment  
**Responsibilities:**
- Integrate FinBERT and other financial transformer models
- Build batch-processing pipelines for news / social text
- Implement composite sentiment scoring (multi-source weighted)
- Map sentiment outputs to tradable signals

**Key module:** `alpha_search.sentiment`  
**Optional dependency:** `pip install "alpha-search[sentiment]"`

---

### 6. Walk-Forward Agent

**Role:** Strategy validation and overfitting detection  
**Responsibilities:**
- Generate rolling train/test splits for time series
- Compute in-sample / out-of-sample degradation
- Implement multiple-comparison correction algorithms
- Produce validation reports that feed into the Terminal UI

**Key module:** `alpha_search.walk_forward`

---

### 7. Portfolio Optimizer Agent

**Role:** Capital allocation and risk management  
**Responsibilities:**
- Implement MVO, risk-parity, and HRP allocation algorithms
- Enforce constraints (long-only, sector limits, max position size)
- Compute covariance matrices with shrinkage estimators
- Output portfolio weights and risk-contribution breakdowns

**Key module:** `alpha_search.portfolio`

---

### 8. Terminal Agent

**Role:** User-facing interfaces  
**Responsibilities:**
- Build and maintain the Streamlit dashboard
- Implement the CLI entry point (`alpha-search`)
- Develop the optional FastAPI REST server
- Wire all other agents into a unified user experience

**Key module:** `alpha_search.terminal`

---

### 9. Global Market Opportunity Agent

**Role:** Multi-strategy, multi-asset opportunity discovery for global markets

**Mission:** Continuously scan global multi-asset markets — US equities (S&P 500, NASDAQ 100, DOW 30), Indian equities (NIFTY 50), cryptocurrencies (BTC, ETH, SOL), forex pairs, and commodities — across momentum, mean-reversion, and statistical-arbitrage dimensions; score and rank actionable opportunities; feed curated trade candidates to the UI and portfolio builder.

**Key capabilities:**
- **Momentum scanning** — 20-day & 50-day ROC, ADX > 25, volume > 1.5x 20-day average across all asset classes
- **Mean-reversion scanning** — z-score deviation > 1.5 sigma from 20-day mean, RSI(14) between 30-40, price within 3% of lower Bollinger Band
- **Statistical arbitrage** — cointegration testing (Engle-Granger), z-score spread deviation, half-life estimation
- **Composite scoring** — weighted multi-factor formula (see below)
- **Multi-asset data acquisition** — yfinance integration for equities, crypto, FX, and commodities
- **Global market coverage** — NIFTY 50, S&P 500, NASDAQ 100, DOW 30, FTSE 100, Crypto, FX, Commodities

**Files owned:**
```
alpha_search/opportunities/
├── __init__.py
├── models.py          # StockOpportunity, PairOpportunity Pydantic models
├── scoring.py         # FinalScore calculator with weighted 6-factor formula
├── scanner.py         # StockOpportunityScanner orchestrator
├── strategies.py      # Momentum, mean-reversion, arbitrage scan engines
├── market_universes.py # Universe definitions for all asset classes
└── config.py          # Scoring weights, thresholds
```

**Handoff protocol:**
| Consumer | Data received | Trigger |
|----------|--------------|---------|
| UI Developer | `list[Opportunity]` + `summary_stats` | Every scan cycle (configurable interval) |
| Portfolio Builder | `opportunities.json` | On "Build Portfolio" button click |
| Risk Dashboard | `max_drawdown`, `sharpe_estimate`, `volatility` | Real-time streaming |

> *"I want to find the best trading opportunities across global markets -- US stocks, Indian equities, crypto, and more -- all in one place."* -- This agent exists to turn that user need into a systematic, repeatable multi-asset discovery pipeline.

**Scoring formula:**
```
Final Score = 0.25 * strategy_signal_strength
            + 0.20 * liquidity_score
            + 0.15 * sentiment_score
            + 0.15 * risk_adjusted_return_score
            + 0.15 * hedgeability_score
            + 0.10 * execution_feasibility_score
```
- Each raw score is normalised to `[0, 1]` before weighting
- Final score is clamped to `[0, 1]` and rounded to 4 decimal places
- Higher is better -- rank descending

**Consumers:**
- `alpha_search/ui/opportunities.py` -- renders opportunity cards
- `alpha_search/ui/portfolio_builder.py` -- adds selected symbols to basket
- `alpha_search/ui/risk_dashboard.py` -- stress-tests opportunity subset

---

## Communication Protocol

Agents communicate via a simple message-passing protocol:

```python
class Task:
    agent: str           # target agent name
    action: str          # method to invoke
    payload: dict        # keyword arguments
    request_id: UUID     # correlation ID

class Result:
    request_id: UUID
    status: Literal["ok", "error"]
    data: Any
    metrics: dict        # timing, memory, etc.
```

In practice, because all agents run in the same Python process, this resolves to ordinary function calls. The protocol exists to support future distributed execution (Redis queue, Celery, etc.).

---

## Conflict Resolution

When two agents produce incompatible outputs (e.g., a signal that the backtest engine cannot consume), the Coordinator applies these rules:

1. **Type mismatch** → Convert via pandas/NumPy coercion if lossless; error otherwise
2. **Index misalignment** → Reindex to union with `fill_value=0.0`; warn
3. **Schema divergence** → Prefer the Signals Agent's output schema as canonical
4. **Metric disagreement** → Recompute from raw equity curve; log discrepancy

---

## Adding a New Agent

To add a 10th agent (e.g., a **Broker Agent** for live execution):

1. Create a new module: `alpha_search/broker/`
2. Implement the agent class with `execute(task) -> Result`
3. Register in `alpha_search/agents/__init__.py`
4. Add tests in `tests/test_broker.py`
5. Update this document

The Coordinator will auto-discover and route tasks to the new agent.
