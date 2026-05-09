# Alpha Search vs OpenBB

OpenBB is an exceptional financial-data terminal. Alpha Search is a quantitative-research operating system. The two are **complementary**, not competitive. Many users will run both.

---

## What OpenBB Does Well

| Strength | Details |
|---|---|
| **Data breadth** | 100+ data sources: equities, crypto, forex, macro, alternatives, fixed income |
| **Unified CLI** | A single command-line interface for every data source |
| **Community** | Large, mature open-source community with extensive documentation |
| **Econometrics** | Integration with statsmodels,arch, and other econometric libraries |
| **Data export** | One-liners to export any dataset to CSV, Excel, or JSON |

If your workflow is: *"I need to pull data from many sources, inspect it quickly, and export it"* — OpenBB is the right tool.

---

## What Alpha Search Adds

| Capability | What It Solves |
|---|---|
| **Backtesting engine** | OpenBB has limited backtest support. Alpha Search provides a fast, vectorised backtester with realistic costs, equity curves, and metrics. |
| **Signal generation** | A library of composable signal primitives (momentum, mean-reversion, ensemble, Boolean composition). |
| **Walk-forward validation** | Rolling-window train/test splits that detect overfitting before capital is at risk. |
| **Sentiment analysis** | FinBERT-powered sentiment scoring for news, social, and earnings transcripts. |
| **Portfolio optimization** | Mean-variance, risk-parity, and HRP allocation engines. |
| **Paper trading** | Simulated execution against live price feeds with fill tracking. |
| **Streamlit UI** | A no-code dashboard for non-technical stakeholders to explore signals and backtests. |

If your workflow is: *"I have an idea for a signal, I want to backtest it, validate it, and paper-trade it"* — Alpha Search is the right tool.

---

## How They Complement Each Other

```
OpenBB                    Alpha Search
------------------        ------------------
Pull macro data  --------> Use as regime
from FRED                  filter in signals

Pull equity      --------> Feed into
OHLCV from                 backtest engine
Yahoo Finance

Screen           --------> Optimize
universe of                portfolio
1000 stocks                allocations

Export to CSV    --------> Load into
                           sentiment pipeline
```

**Recommended dual workflow:**

1. Use **OpenBB** to discover, explore, and export data
2. Use **Alpha Search** to generate signals, backtest, validate, and optimise
3. Use **OpenBB** again to monitor live performance and macro context

---

## Feature Matrix

| Feature | OpenBB | Alpha Search |
|---|---|---|
| 100+ data sources | ✅ | ❌ (focused on Yahoo + Binance) |
| CLI data exploration | ✅ | ❌ (Python API + Streamlit) |
| Backtesting | ⚠️ (basic) | ✅ (vectorised, costs, metrics) |
| Signal generation | ❌ | ✅ (primitives + ensemble) |
| Walk-forward validation | ❌ | ✅ |
| Sentiment (FinBERT) | ❌ | ✅ |
| Portfolio optimization | ❌ | ✅ (MVO, RP, HRP) |
| Paper trading | ❌ | ✅ |
| Streamlit dashboard | ❌ | ✅ |
| REST API | ❌ | ✅ (optional FastAPI) |
| Econometrics | ✅ | ⚠️ (via pandas/numpy) |
| Data export (CSV/Excel) | ✅ | ⚠️ (pandas I/O) |

---

## Migration Guide: OpenBB → Alpha Search

### Moving Data

OpenBB exports DataFrames that Alpha Search can consume directly:

```python
# OpenBB
from openbb import obb
aapl = obb.equity.price.historical("AAPL", start_date="2023-01-01")

# Alpha Search accepts the same DataFrame
from alpha_search.backtest import BacktestEngine
from alpha_search.signals import momentum

signal = momentum(aapl.close, window=20)
engine = BacktestEngine(initial_capital=100_000)
result = engine.run(aapl.close, signal)
```

### Replacing Workflows

| OpenBB Command | Alpha Search Equivalent |
|---|---|
| `obb.equity.price.historical` | `qr.data.get_prices("AAPL", ...)` |
| `obb.crypto.price.historical` | `qr.data.get_prices("BTC-USD", ...)` |
| `obb.economy.fred_series` | Use `pandas_datareader` or load DuckDB table |
| Basic plotting | `result.equity_curve.plot()` or Streamlit UI |

### Running Both Side-by-Side

There is no conflict. Install both in the same environment:

```bash
pip install openbb alpha-search
```

They share pandas and numpy as dependencies and interoperate naturally via DataFrames.

---

## Summary

- **OpenBB** = the best way to *access* financial data
- **Alpha Search** = the best way to *research and trade* on that data

Use OpenBB to pull the data. Use Alpha Search to turn it into alpha.
