# Alpha Search

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/alpha-search/alpha-search/actions/workflows/ci.yml/badge.svg)](https://github.com/alpha-search/alpha-search/actions)
[![Deploy](https://github.com/alpha-search/alpha-search/actions/workflows/deploy.yml/badge.svg)](https://github.com/alpha-search/alpha-search/actions)
[![Open In Colab](https://colab.research.google.com/assets/colab_badge.svg)](https://colab.research.google.com/github/alpha-search/alpha-search/blob/main/notebooks/Alpha_Search_Demo.ipynb)

**The Agent-Powered Quantitative Research Framework**

> **Version 0.2.2** — Data Platform with 37 sources, Agent Swarm collaboration, and Persistent Memory
>
> Previously developed internally as Quant.OS. Rebranded to Alpha Search before public launch.

---

## What's New in v0.2.2

**13 correctness and security fixes** from a comprehensive code review — full details in [`CHANGES_v0.2.2.md`](CHANGES_v0.2.2.md).

| Area | Change |
|------|--------|
| **Agent Swarm** | `QuantEngineerAgent` now runs real `BacktestEngine` backtests (was random simulation). Sign-offs are conditional on critique severity. Word-boundary ticker matching fixes MET/META collision. |
| **Risk / Drawdown** | Unified negative drawdown convention (`-0.25` = 25% DD) throughout. `RiskManagerAgent` alerts now fire correctly. |
| **Backtest** | Position signals clipped to `[-1, 1]` (prevents >100% leverage). Transaction costs use portfolio notional value (was per-share, underestimating costs ~1000×). |
| **Signals** | RSI uses Wilder's EMA (matches literature). RSI divide-by-zero guard added. |
| **Pairs Trading** | `_hedge_ratio()` gains a `rolling_window` parameter for time-varying hedge-ratio estimation. Log(0) tickers explicitly excluded with a warning before `np.log()`. |
| **Security** | `CacheManager` enforces parquet-only deserialization — `pickle.loads()` removed. |
| **Memory** | `get_unresolved_blockers()` now filters `status="active"` correctly. Schema init failures logged and re-raised when >50% fail. |
| **Architecture** | `CritiqueGenerator` and `ConsensusBuilder` extracted from the `AgentSwarm` god class. `DataEngineerAgent` validation vectorized. |
| **Tests** | 52 new tests: `QuantEngineerAgent` signal construction, rolling hedge ratio, and a full end-to-end data → signals → backtest → agents → memory integration test. Total: **174 tests**. |

---

## What is Alpha Search?

Alpha Search is a production-grade Python framework that unifies the entire quantitative research workflow in a single, coherent toolchain. From raw market data to executable signals, from sentiment analysis to walk-forward validation, from portfolio construction to paper-traded simulation — every stage of the quant lifecycle is covered under one roof. It is built with the rigor expected by institutional researchers and the ergonomics needed for rapid iteration.

The framework is **open-source (MIT)** and **local-first**. Data is cached in DuckDB on your own machine, so you own every tick, every inference, and every backtest result. No SaaS lock-in, no per-seat pricing, no rate limits on your imagination. Whether you are a solo quant researcher, a hedge fund building proprietary strategies, or a fintech startup shipping analytics products, Alpha Search gives you full control.

At its core, Alpha Search treats quantitative research as a directed pipeline: **Data → Sentiment → Research → Signals → Backtest → Walk-Forward Validation → Portfolio → Paper Execution → Terminal UI**. Each module can be used independently, or wired together through the `Terminal` facade for a seamless end-to-end experience.

---

## Quick Start

### Option 1: Google Colab (Fastest — No Installation)

[![Open In Colab](https://colab.research.google.com/assets/colab_badge.svg)](https://colab.research.google.com/github/alpha-search/alpha-search/blob/main/notebooks/Alpha_Search_Demo.ipynb)

Run the full pipeline in your browser with one click.

### Option 2: Local Installation

```bash
pip install alpha-search          # or pip install "alpha-search[all]"
alpha-search --universe AAPL MSFT  # Launch Streamlit terminal
```

## Python Quickstart

```python
from alpha_search import Terminal

# Initialize with your universe
t = Terminal(universe=["AAPL", "MSFT"])

# Fetch OHLCV data
df = t.data.get_prices("AAPL", "2020-01-01", "2023-12-31")

# Generate a momentum signal
signal = t.signals.momentum(df["Close"], window=20)

# Run a vectorized backtest
result = t.backtest.run(df, signal, initial_capital=100_000)
print(result.metrics)
```

---

## Installation

### PyPI (Recommended)

```bash
pip install alpha-search
```

### With All Optional Dependencies

```bash
pip install "alpha-search[all]"
```

This includes:

- **binance**: Crypto data via `python-binance`
- **nlp**: FinBERT sentiment via `transformers` + `torch`
- **optimize**: Portfolio optimization via `scipy`

### Development

```bash
git clone https://github.com/alpha-search/alpha-search.git
cd alpha-search
pip install -e ".[dev]"
```

Dev dependencies include `pytest`, `pytest-cov`, `black`, `mypy`, and `ruff`.

---

## Opportunity Discovery

Alpha Search includes a dedicated **Global Market Opportunity Agent** that acts as the intelligence layer between raw market data and the frontend opportunity board. This is not a static stock screener — it is a continuously running discovery engine that hunts for actionable trade setups across global multi-asset markets: **US equities** (S&P 500, NASDAQ 100, DOW 30), **Indian equities** (NIFTY 50), **cryptocurrencies** (BTC, ETH, SOL, XRP, ADA), **forex** pairs, and **commodities**.

### How it works

1. **Scan** — Every cycle, the agent pulls latest OHLCV data for the selected universe via yfinance:
   - S&P 500, NASDAQ 100, DOW 30 for US equities
   - NIFTY 50 for Indian equities
   - BTC-USD, ETH-USD, SOL-USD, XRP-USD, ADA-USD, BNB-USD for crypto
   - Major forex pairs (EUR/USD, GBP/USD, USD/JPY, etc.)
   - Commodity futures (Gold, Crude Oil, Natural Gas, etc.)
2. **Analyse** — Each instrument is evaluated through three parallel strategy lenses:
   - **Momentum** — 20-day & 50-day ROC with ADX trend-strength confirmation and volume surge filter
   - **Mean Reversion** — z-score deviation from 20-day mean, RSI(14) oversold confirmation, proximity to lower Bollinger Band
   - **Statistical Arbitrage** — cointegration testing (Engle-Granger), spread z-score monitoring, half-life estimation for pair-trading candidates
3. **Score** — A composite score is computed for every passing instrument using a weighted 6-factor formula:
   ```
   Final Score = 0.25 * strategy_signal_strength
               + 0.20 * liquidity_score
               + 0.15 * sentiment_score
               + 0.15 * risk_adjusted_return_score
               + 0.15 * hedgeability_score
               + 0.10 * execution_feasibility_score
   ```
   Each sub-score is normalised to `[0, 1]` before weighting. The scoring formula is market-agnostic and works across all asset classes.
4. **Rank & Deliver** — Results are sorted descending by composite score, capped at top-N (default 20), and pushed to the frontend opportunity board. The board is powered by this agent — every instrument displayed has passed a rigorous, multi-factor quantitative filter, not a random or popularity-based selection.

### Research & Educational Use Only

The Global Market Opportunity Agent is provided for **research and educational purposes only**. It does not constitute investment advice. The scoring formula is fully transparent and customisable via `alpha_search/opportunities/config.py` — users are encouraged to experiment with weights, thresholds, and strategy parameters to build their own discovery logic.

---

## Try It in Google Colab

Launch the full Alpha Search pipeline in your browser — no installation required:

[![Open In Colab](https://colab.research.google.com/assets/colab_badge.svg)](https://colab.research.google.com/github/alpha-search/alpha-search/blob/main/notebooks/Alpha_Search_Demo.ipynb)

The notebook demonstrates:
- Fetching real market data for US Top 20 equities
- Running all 3 strategy backtests (momentum, mean reversion, arbitrage)
- Launching the 5-agent swarm with critique loops
- Viewing agent critiques, consensus, and sign-offs
- Visualizing performance and correlation matrices
- Saving results to persistent memory

---

## Data Source Platform (37 Sources)

Alpha Search is designed as an **open data source platform** where researchers can discover, register, and use financial data sources through a unified interface. The platform currently includes **37 data sources** across **7 categories**:

| Category | Sources | Live |
|----------|---------|------|
| **Stocks** | Yahoo Finance, Alpha Vantage, Polygon.io, FMP, Tiingo, EODHD, Twelve Data | 3 |
| **Crypto** | CoinGecko, Binance, CryptoCompare, Messari, Glassnode, CoinMarketCap | 2 |
| **Forex** | OANDA, Forex Python | 0 |
| **Macro** | FRED, World Bank, IMF, OECD, Trading Economics | 1 |
| **News & Sentiment** | NewsAPI, Finnhub News, Reddit API, Twitter/X API, GDELT | 0 |
| **Fundamentals** | SEC EDGAR, SimFin, OpenFIGI, Nasdaq Data Link | 1 |
| **Alternative** | Open-Meteo, GitHub Activity, AltStack, Bursa Malaysia, NSE India | 1 |

### Using the Data Source Platform

```python
from alpha_search.data_sources import registry

# See what's available
print(f"Total sources: {registry.count()}")
print(f"Live now: {registry.count_live()}")
print(f"Available without API key: {len([s for s in registry.list_available() if not s.requires_api_key])}")

# Browse by category
for meta in registry.list_by_category("macro"):
    print(f"  {meta.name}: {meta.description}")

# Use a source
fred = registry.get("fred")
df = fred.fetch_macro("GDP")  # US GDP time series
```

### Activating Sources

Some sources require an API key:

| Source | Environment Variable | Free Tier |
|--------|---------------------|-----------|
| Alpha Vantage | `ALPHA_VANTAGE_API_KEY` | 25 calls/day |
| Polygon.io | `POLYGON_API_KEY` | 5 calls/min |
| FRED | `FRED_API_KEY` (optional) | 120 calls/min |
| CoinGecko | `COINGECKO_API_KEY` (optional) | 10-30 calls/min |
| SEC EDGAR | `SEC_USER_AGENT` | Unlimited |

---

## Agent Swarm Collaboration

Alpha Search includes a **multi-agent collaboration system** where 5 specialized agents work together, critique each other's outputs, and build consensus on strategy recommendations:

| Agent | Role |
|-------|------|
| **DataEngineerAgent** | Validates data quality, flags missing data and suspicious jumps |
| **OpportunityAgent** | Ranks candidates by momentum, mean reversion, and arbitrage signals |
| **QuantEngineerAgent** | Builds and backtests signals with transaction costs |
| **ResearchAgent** | Provides sentiment analysis and research context |
| **RiskManagerAgent** | Reviews strategies against drawdown and position limits |

### The Critique Loop

Agents don't just produce outputs — they **critique each other** in two rounds:

1. **Round 1**: Every agent reviews every other agent's work and issues structured critiques (data quality, signal quality, risk concerns, improvements)
2. **Improvement**: Agents incorporate feedback and revise their strategies
3. **Round 2**: All agents review the updated strategies
4. **Consensus**: Final recommendation with agent sign-offs

```python
from alpha_search.agents.swarm import AgentSwarm
from alpha_search.agents.roles import (
    DataEngineerAgent, QuantEngineerAgent, RiskManagerAgent,
    ResearchAgent, OpportunityAgent,
)

# Set up the swarm
swarm = AgentSwarm()
swarm.register("data_engineer", DataEngineerAgent())
swarm.register("opportunity_agent", OpportunityAgent())
swarm.register("quant_engineer", QuantEngineerAgent(cost_model))
swarm.register("research_agent", ResearchAgent())
swarm.register("risk_manager", RiskManagerAgent())

# Run full collaboration with critique loops
result = swarm.run_collaboration(tickers=us_top_20, prices=price_data)

# View critiques
for c in result["critiques"]:
    print(f"{c['from_agent']} → {c['to_agent']}: {c['message']}")

# View consensus
print(result["consensus"])
```

---

## Persistent Memory Layer

Alpha Search includes a **dual-write persistent memory system** that stores agent activity, critiques, strategies, and decisions across sessions using DuckDB (with SQLite fallback):

```python
from alpha_search.memory.store import MemoryStore
from alpha_search.memory.journal import AgentJournal

# Create memory store (DuckDB with automatic SQLite fallback)
store = MemoryStore(db_path="./alpha_memory.db")
journal = AgentJournal(store)

# Log agent activity
journal.log_critique(critique_message)
journal.log_strategy("momentum_v2", "quant_engineer", strategy_dict)
journal.log_event("round_complete", "swarm", {"round": 1})

# Query memory
from alpha_search.memory.retrieval import MemoryRetriever
retriever = MemoryRetriever(store)
records = retriever.query(record_type="critique", limit=50)
```

---

## Architecture

```
alpha_search/
├── core/              # Pydantic models, base classes, config, exceptions
├── data/              # Multi-source providers (Yahoo Finance, Binance), DuckDB cache, normalizer
├── data_sources/      # Data Source Platform — 37 sources across 7 categories (plugin architecture)
├── signals/           # Technical (momentum, RSI, Bollinger), fundamental, ensemble signals
├── backtest/          # Vectorized engine, performance metrics, walk-forward validation
├── sentiment/         # FinBERT NLP, NewsAPI, social-media aggregation, composite scoring
├── portfolio/         # Construction, mean-variance optimization, risk metrics (VaR, CVaR)
├── execution/         # Paper-trading simulation, broker adapter stubs, pre-trade risk controls
├── opportunities/     # Global multi-asset opportunity discovery (momentum, mean reversion, arbitrage)
├── agents/            # Multi-agent swarm collaboration framework with critique loops
├── memory/            # Persistent memory — DuckDB + Markdown dual-write for agent activity
├── research/          # Real data pipeline, report writer, universes, metrics
├── api/               # FastAPI REST endpoints for headless / programmatic access
├── ui/                # Streamlit interactive dashboard with Plotly visualizations
└── terminal.py        # Main facade — wire everything together in 5 lines of Python
```

![Alpha Search Pipeline](docs/alpha_search_pipeline.png)

---

## Alpha Search vs OpenBB

**OpenBB** is the gold standard for financial *data discovery*. It aggregates 100+ data sources — from equities and crypto to macro and alternatives — and wraps them in a beautiful terminal UI for exploration. If your primary need is "find and inspect data," OpenBB is unbeatable.

**Alpha Search** is the research layer that turns data into *actionable strategies*. While OpenBB stops at the data frontier, Alpha Search continues through the entire quant pipeline: sentiment inference, signal generation, vectorized backtesting, walk-forward validation, portfolio optimization, and paper-trading simulation. It is designed for researchers who need to go from "I have data" to "I have a validated strategy" without stitching together five different libraries.

> **Use OpenBB to discover data. Use Alpha Search to build strategies.**

| Feature | OpenBB | Alpha Search |
|---------|--------|----------|
| Data aggregation | 100+ sources | **37 sources** across 7 categories (8 live now) |
| Data source platform | Terminal plugins | **Plugin architecture with unified ABC interface** |
| Sentiment analysis | — | FinBERT, NewsAPI, social media, composite scoring |
| Backtesting | — | Vectorized engine with PnL, Sharpe, drawdown metrics |
| Walk-forward validation | — | Rolling train / test splits, out-of-sample testing |
| Portfolio optimization | — | Mean-variance, risk-parity, CVaR constraints |
| Paper trading | — | Simulated execution with slippage and risk controls |
| **Agent swarm** | — | **5 agents with 2-round critique loops & consensus** |
| **Persistent memory** | — | **DuckDB + Markdown dual-write across sessions** |
| Terminal UI | OpenBB Terminal | Streamlit + Plotly interactive dashboard |
| REST API | — | FastAPI endpoints for programmatic access |
| License | AGPL-3.0 | MIT |

### Why MIT matters for quants

OpenBB ships under **AGPL-3.0**, a strong copyleft license that can create friction for hedge funds, proprietary trading desks, and commercial fintech products. Alpha Search uses the **MIT license**, which means you can embed it in proprietary tools, ship it inside SaaS products, or build closed-source strategies on top of it without legal ambiguity. The only requirement is attribution — freedom and respect, both ways.

---

## Modules

| Module | Purpose |
|--------|---------|
| `alpha_search.core` | Shared Pydantic models, configuration, and custom exceptions |
| `alpha_search.data` | Multi-asset data ingestion (equities, crypto) with DuckDB caching |
| `alpha_search.data_sources` | **Data Source Platform** — 37 sources, plugin architecture, unified interface |
| `alpha_search.signals` | Technical indicators, cross-sectional signals, and ensemble builders |
| `alpha_search.backtest` | Fast, vectorized backtest engine with performance analytics |
| `alpha_search.sentiment` | NLP-driven sentiment from news, social media, and financial text |
| `alpha_search.portfolio` | Construction, mean-variance optimization, and risk attribution |
| `alpha_search.execution` | Paper-trading simulation with realistic slippage and risk checks |
| `alpha_search.opportunities` | Global multi-asset opportunity discovery — US equities, Indian equities, crypto, FX, commodities |
| `alpha_search.agents` | **Agent Swarm** — 5-agent collaboration with structured critique loops |
| `alpha_search.memory` | **Persistent Memory** — DuckDB + Markdown dual-write across sessions |
| `alpha_search.research` | Real data pipeline, report writer, market universes, metrics |
| `alpha_search.api` | FastAPI REST layer for headless deployment and micro-service integration |
| `alpha_search.ui` | Streamlit dashboard for visual exploration and real-time monitoring |

---

## CLI

After installation, the `alpha-search` command is available globally:

```bash
# Launch the Streamlit terminal UI with a default universe
alpha-search --universe AAPL MSFT GOOGL

# You can also pass a universe file
alpha-search --universe-file ./my_universe.txt
```

The CLI is a thin wrapper around `alpha_search.terminal:main`. For programmatic access, import the `Terminal` class directly (see Python Quickstart above).

---

## Links

- **Documentation**: [https://alpha-search.readthedocs.io](https://alpha-search.readthedocs.io)
- **GitHub**: [https://github.com/alpha-search/alpha-search](https://github.com/alpha-search/alpha-search)
- **PyPI**: [https://pypi.org/project/alpha-search](https://pypi.org/project/alpha-search)
- **Issue Tracker**: [https://github.com/alpha-search/alpha-search/issues](https://github.com/alpha-search/alpha-search/issues)

---

## License

MIT License. See [LICENSE](LICENSE) for details.
