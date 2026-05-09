# Alpha Search — Testing Plan & Next Steps

> **Current Status: v0.2.1** | 104 tests passing | CI green on Python 3.9-3.12
> **Coverage: 35% (104/300 scenarios)** | **Goal v0.3: 60% (180/300)**

---

## 1. How Alpha Search Works — Pipeline Flow

```
USER INPUT
    |
    v
[1] DATA SOURCES (40 sources) -----> [1d] CACHE (DuckDB/SQLite)
    |                                        |
    | yfinance (live)                        v
    | binance (live)                  [6] MEMORY LAYER
    | newsapi (live)                       |    DuckDB + Markdown journals
    | alpha_vantage, FRED...               |    StrategyMemory, AgentJournal
    v                                      |    MemoryStore, MemoryRetriever
[2] SIGNALS ENGINE                       |
    | RSI, MACD, Bollinger, ADX           v
    | z-score, MA crossover          [7] AGENT SWARM (5 roles)
    v                                      |    DataEngineer -> validate data
[2b] OPPORTUNITIES                       |    QuantEngineer -> build signals
    | Momentum (60d rank)                  |    RiskManager -> check drawdowns
    | Mean reversion (z-score)             |    ResearchAgent -> sentiment
    | Statistical arbitrage (pairs)        |    OpportunityAgent -> rank
    v                                      |    2-round critique + consensus
[2c] SENTIMENT                           |
    | FinBERT (financial NLP)              v
    | VADER (social media)           [8] REPORTS (8 outputs)
    | TextBlob (fallback)                  |    Markdown + CSV + metadata.json
    v                                      |    AgentSwarmReportGenerator
[3] BACKTEST ENGINE                      |    StrategyReportGenerator
    | Vectorized pandas
    | CostModel (commission + slippage)
    | WalkForwardValidator
    v
[3b] VALIDATION
    | Train/test split
    | Overfitting detection
    | Regime detection
    v
[4] PORTFOLIO OPTIMIZATION (8 methods)
    | Equal Weight, Inverse Vol, Risk Parity
    | Mean-Variance, Min Variance
    | Max Diversification, Black-Litterman, HRP
    v
[4b] RISK MANAGEMENT
    | VaR, CVaR, Max Drawdown limit
    | Position sizing, Stop-loss
    | Stress testing
    v
[5] EXECUTION (paper trading)
    | Alpaca, Interactive Brokers
    | Slippage model
    v
    FEEDBACK LOOPS:
    Memory <- learns from past results
    Agents <- critique and improve signals
    Backtest <- optimize portfolio weights
```

---

## 2. What Is Fully Tested (Tier 1) — 104 tests

| Module | Tests | Description |
|--------|------:|-------------|
| `alpha_search/__init__` | 5 | Package imports, version, exports |
| `signals/technical.py` | 8 | RSI, MACD, Bollinger, z-score, ADX |
| `backtest/engine.py` | 12 | Vectorized backtest, CostModel, trades |
| `portfolio/optimization.py` | 6 | Equal weight, inverse vol, risk parity |
| `opportunities/` | 10 | Scanner, strategies, FinalScore |
| `memory/` | 15 | DuckDB CRUD, SQLite fallback, dual-write |
| `memory/models.py` | 8 | Pydantic validation, STATUS_VALUES |
| `agents/` | 12 | 5 roles, critique loops, consensus |
| `data_sources/` | 8 | Registry, 37 sources, 3 live |
| `data/cache.py` | 6 | DuckDB cache, pickle fallback |
| `research/` | 14 | Universes, metrics, pipelines, reports |
| **Total** | **104** | **All passing on Python 3.9-3.12** |

---

## 3. What Needs Testing (Next Priority Order)

### Sprint 1: Real Data Validation (High Priority)

| # | Test Scenario | Status | How to Run |
|---|--------------|--------|-----------|
| 1 | **Fetch real data for 12 tickers** | Not tested | `python scripts/run_real_data_research.py` |
| 2 | **Backtest momentum on real prices** | Partial | Uses `alpha_search.backtest.engine` |
| 3 | **Backtest mean reversion on real prices** | Partial | Compare to buy-and-hold |
| 4 | **Portfolio optimization on real returns** | Partial | 3 methods tested |
| 5 | **Sentiment analysis on real news** | Not tested | `newsapi.fetch_sentiment(tickers)` |
| 6 | **Full pipeline: data → signals → backtest → report** | Not tested | `run_full_pipeline(output_dir)` |

### Sprint 2: Stress Tests (Medium Priority)

| # | Test Scenario | Why It Matters |
|---|--------------|---------------|
| 7 | **S&P 500 universe (503 tickers)** | Memory and performance limits |
| 8 | **10 years of daily data** | Large dataset handling |
| 9 | **All 7 signals simultaneously** | Signal combination and correlation |
| 10 | **Walk-forward validation (rolling windows)** | Overfitting detection |
| 11 | **Monte Carlo simulation** | Randomized returns, stress test |
| 12 | **Regime detection (HMM)** | Bull/bear/sideways market states |

### Sprint 3: Advanced Strategies (Low Priority)

| # | Test Scenario | Status |
|---|--------------|--------|
| 13 | **Crypto strategies (BTC, ETH)** | Not implemented |
| 14 | **India Nifty 50** | Universe defined, not tested |
| 15 | **Statistical arbitrage with ADF test** | Needs scipy adfuller |
| 16 | **Options strategies** | Not implemented |
| 17 | **Intraday data (1min/5min)** | Not implemented |
| 18 | **Paper trading (Alpaca)** | Not implemented |

### Sprint 4: Platform Integration

| # | Test Scenario | Target Platform |
|---|--------------|-----------------|
| 19 | **pip install alpha-search** | PyPI |
| 20 | **Google Colab compatibility** | `!pip install alpha-search` |
| 21 | **Jupyter notebook interactive** | Local/Colab |
| 22 | **Docker build and run** | `docker build .` |
| 23 | **Data source failover chain** | yfinance → alpha_vantage → synthetic |
| 24 | **Concurrent backtests** | ThreadPool/multiprocessing |

---

## 4. How to Run Each Test Scenario

### Scenario 1: Fetch Real Data
```bash
python scripts/run_real_data_research.py \
    --start 2019-01-01 \
    --end latest \
    --universe us_large_cap \
    --output-dir alpha_search/reports
```
**Expected**: 12 CSV files + Markdown report in `alpha_search/reports/latest/`

### Scenario 2: Backtest Single Strategy
```python
from alpha_search.research.metrics import compute_all_metrics
from alpha_search.signals.technical import rsi, ma_crossover

# Load data
df = pd.read_csv('alpha_search/reports/latest/price_data.csv')

# Build signal
signal = rsi(df['close'], window=14)

# Backtest
returns = df['close'].pct_change()
strategy_returns = (signal > 50).shift(1) * returns
metrics = compute_all_metrics(strategy_returns)
print(metrics)
```

### Scenario 3: Run Full Pipeline
```python
from alpha_search.research.swarm_pipeline import run_swarm_pipeline

results = run_swarm_pipeline(output_dir='reports')
print(results['swarm_results']['critiques'])
print(results['pipeline_results']['momentum'])
```

### Scenario 4: Google Colab Test
```python
# In a Colab cell:
!pip install git+https://github.com/alpha-search/alpha-search.git

import alpha_search
from alpha_search.research.universes import US_LARGE_CAP
from alpha_search.research.metrics import compute_all_metrics

print(alpha_search.__version__)
print(US_LARGE_CAP.tickers)
```

### Scenario 5: Agent Swarm on Real Data
```python
from alpha_search.agents import AgentSwarm, DataEngineerAgent, QuantEngineerAgent
from alpha_search.agents import RiskManagerAgent, ResearchAgent, OpportunityAgent

swarm = AgentSwarm()
swarm.register('data_engineer', DataEngineerAgent())
swarm.register('quant_engineer', QuantEngineerAgent())
swarm.register('risk_manager', RiskManagerAgent())
swarm.register('research_agent', ResearchAgent())
swarm.register('opportunity_agent', OpportunityAgent())

result = swarm.run_collaboration(tickers, prices)
print(f"Critiques: {len(result['critiques'])}")
print(f"Consensus: {result['consensus'][:200]}")
```

---

## 5. Test Results Log

| Date | Test | Result | Notes |
|------|------|--------|-------|
| 2025-01-09 | Unit tests (104) | PASS | All Python 3.9-3.12 |
| 2025-01-09 | CI/CD workflow | PASS | Both workflows green |
| 2025-01-09 | Ruff lint | PASS | 0 errors |
| 2025-01-09 | Agent swarm (synthetic) | PASS | 13 critiques, consensus |
| 2025-01-09 | Real data pipeline (fallback) | PASS | 11 output files |
| 2025-01-09 | Report generation | PASS | Markdown + CSV + JSON |
| **PENDING** | Real data (yfinance) | **NEEDS TEST** | Run locally |
| **PENDING** | Backtest on real prices | **NEEDS TEST** | Compare to SPY |
| **PENDING** | Sentiment on real news | **NEEDS TEST** | newsapi required |
| **PENDING** | Google Colab | **NEEDS TEST** | `!pip install` |
| **PENDING** | Docker build | **NEEDS TEST** | `docker build .` |
| **PENDING** | S&P 500 stress test | **NEEDS TEST** | 503 tickers |

---

## 6. Files Reference

| Diagram | Path |
|---------|------|
| Pipeline architecture | `docs/alpha_search_pipeline.png` |
| Testing roadmap | `docs/alpha_search_testing_roadmap.png` |
| This document | `TESTING_PLAN.md` |

---

*RESEARCH / EDUCATIONAL PURPOSES ONLY. NOT INVESTMENT ADVICE.*
*Alpha Search v0.2.1 — github.com/alpha-search/alpha-search*
