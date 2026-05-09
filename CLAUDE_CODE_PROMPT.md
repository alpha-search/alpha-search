# Alpha Search — Claude Code Continuation Prompt

Copy-paste this entire message into Claude Code to continue development.

---

## Project Overview

You are working on **Alpha Search**, an open-source quantitative research framework written in Python. The codebase is at `/path/to/alpha-search` (clone from https://github.com/alpha-search/alpha-search).

**Current version:** 0.2.2  
**Python:** 3.9+  
**License:** MIT  
**Tests:** 122 pass, 0 fail  
**Ruff:** Clean  
**CI/CD:** GitHub Actions (ci.yml + deploy.yml) both green

---

## Architecture

```
alpha_search/
├── core/              # Pydantic models, base classes, exceptions
├── data/              # Yahoo Finance, Binance providers, DuckDB cache
├── data_sources/      # Plugin platform — 37 sources, ABC interface
│   ├── base.py        # DataSource ABC + SourceMeta + DataSourceRegistry
│   ├── providers/     # Live: alpha_vantage.py
│   ├── yfinance_source.py, fred.py, coingecko.py, sec_edgar.py, polygon.py
│   └── [30+ stubs]
├── signals/           # Momentum, RSI (Wilder EMA), Bollinger, z-score
├── backtest/          # Vectorized engine, metrics (negative drawdown), costs
├── sentiment/         # FinBERT NLP, NewsAPI aggregation
├── portfolio/         # Mean-variance optimization, risk metrics
├── execution/         # Paper trading, risk controls
├── opportunities/     # Momentum, mean reversion, arbitrage (max_tickers)
├── agents/            # Multi-agent swarm with critique loops
│   ├── swarm.py       # Orchestrator (8-phase pipeline)
│   ├── critique_generator.py   # Cross-agent critiques + improvements
│   ├── consensus_builder.py    # Consensus text + conditional sign-offs
│   └── roles.py       # 5 agents (DataEngineer, QuantEngineer, RiskManager, Research, Opportunity)
├── memory/            # DuckDB + Markdown dual-write persistent memory
├── research/          # Real data pipeline, universes, metrics, report writer
├── api/               # FastAPI REST endpoints
├── ui/                # Streamlit dashboard
└── terminal.py        # Main facade
```

---

## Key Design Decisions Already Made

1. **Drawdown convention is NEGATIVE** — `-0.20` means 20% drawdown. All code uses this.
2. **BacktestEngine is real, not simulated** — `QuantEngineerAgent` accepts `BacktestEngine` + `CostModel` via `__init__` and runs per-ticker backtests on historical prices. Fallback is deterministic (no RNG).
3. **Agent sign-offs are conditional** — `XX` when agent has critical critiques, with per-agent issue counts.
4. **Ticker matching uses regex word boundaries** — `\bMETA\b` prevents MET matching META.
5. **CostModel uses portfolio notional** — `turnover * portfolio_value * rate`, not per-share price.
6. **RSI uses Wilder's EMA** — `ewm(alpha=1/window)`, matching the `_rsi()` in strategies.py.
7. **AgentSwarm delegates** — `CritiqueGenerator` and `ConsensusBuilder` are separate classes. Swarm handles orchestration only.

---

## Recent Changes (Just Applied)

### P0 Fixes (Critical)
- **#1** Replaced simulated RNG backtest with real BacktestEngine in QuantEngineerAgent
- **#2** Fixed max_drawdown sign convention to negative throughout codebase
- **#3** Fixed substring ticker matching → regex word boundaries
- **#4** Added non-positive price validation before np.log() in arbitrage_scan
- **#5** Made agent sign-offs conditional based on actual critique counts

### P1 Fixes (High)
- **#18** Added 18 integration tests for AgentSwarm (test_agent_swarm.py)
- **#27** Added position clipping [-1, 1] in backtest engine
- **#28** Fixed CostModel to use portfolio notional value

### P2 Fixes (Medium)
- **#8** _all_tickers() supports >5 char tickers (RELIANCE.NS, BRK-B)
- **#10** RSI uses Wilder's EMA instead of simple rolling mean
- **#24** arbitrage_scan has max_tickers=50 with variance pre-filter

### P3 Fixes (Architecture)
- **#6** Extracted CritiqueGenerator and ConsensusBuilder from AgentSwarm
- **#26** Vectorized DataEngineerAgent.validate_data() with pandas matrix ops

---

## Remaining Issues to Address

Read `REVIEW.md` in the repo for full details. Key remaining items:

### Medium Priority
- **#7** — AgentJournal._flush() needs retry + dead-letter queue (swallows DB errors silently)
- **#15** — z_score NaN handling edge case in signals/technical.py
- **#19** — More unit tests for QuantEngineerAgent signal construction
- **#21** — Full end-to-end integration test (data → signals → backtest → agents → memory)
- **#25** — AgentJournal._local list grows unbounded during long runs

### Low Priority
- **#9** — Remove QuantEngineerAgent `seed` parameter (now uses real engine)
- **#11** — MemoryStore.initialize() should log/raise on schema failures
- **#12** — _parse_iso() can use datetime.fromisoformat()
- **#13** — __mean_rev_rankings computed but unused (dead code)
- **#16** — MIN_HISTORY_DAYS hardcoded at 60 (too strict for short backtests)
- **#17** — `:.1f` float formatting quirk in cointegration scores
- **#22** — SQL injection via LIKE wildcard in tag search (low severity, internal)
- **#29** — Sharpe ratio uses flat risk-free rate (should use FRED series)
- **#30** — Mean reversion z-score window 20 → 60 days
- **#31** — ResearchAgent fallback should mark results as synthetic
- **#33** — README live source counts need updating

### Future Work (Not in REVIEW)
- Convert more data source stubs to live (NewsAPI, Finnhub, Reddit API)
- S&P 500 stress test (503 tickers)
- Intraday data support (1-min, 5-min bars)
- Walk-forward validation with rolling windows
- Monte Carlo simulation for stress testing
- Streamlit dashboard for real-time swarm monitoring
- PyPI publish: `pip install alpha-search`

---

## Running Tests

```bash
# Install
cd alpha-search
pip install -e ".[dev]"

# Run all tests (122 should pass)
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_agent_swarm.py -v

# Lint
cd alpha_search && ruff check .

# Verify import
python -c "import alpha_search; print(alpha_search.__version__)"
```

---

## Your Task

1. Read `REVIEW.md` for complete issue descriptions
2. Read `CHANGES_v0.2.2.md` for what was already fixed
3. Address remaining medium-priority issues (#7, #15, #19, #21, #25)
4. Run tests after every change: `python -m pytest tests/ -x -v`
5. Keep ruff clean: `ruff check alpha_search/ tests/`
6. Commit incrementally with descriptive messages

When you're done, update CHANGES_v0.2.2.md with what you fixed and push to main.
