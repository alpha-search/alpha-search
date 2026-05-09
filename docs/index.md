# Alpha Search Documentation

> **The Operating System for Quantitative Research**

---

## Welcome

Alpha Search is a Python-native quantitative research platform that unifies data access, signal generation, backtesting, sentiment analysis, and portfolio optimization into a single cohesive toolkit. It is designed for quant researchers, systematic traders, and asset managers who want to move from idea to validated strategy quickly — without stitching together half a dozen disparate libraries.

## What Alpha Search Provides

| Capability | Description |
|---|---|
| **Unified Data Layer** | Fetch OHLCV from Yahoo Finance, Binance, and other providers through a single API. Local DuckDB caching eliminates redundant network calls. |
| **Signal Generation** | Vectorised primitives: momentum, mean-reversion, MA crossover, z-score, ensemble composition, and Boolean logic (AND / OR). |
| **Backtest Engine** | Fast, fully vectorised backtesting with realistic transaction costs, equity-curve tracking, and Sharpe / drawdown / return metrics. |
| **Walk-Forward Validation** | Rolling-window train/test splits that detect in-sample overfitting before you risk real capital. |
| **Sentiment Analysis** | FinBERT-powered financial sentiment scoring with batch processing and composite aggregation across multiple news sources. |
| **Portfolio Optimization** | Mean-variance, risk-parity, and hierarchical risk parity (HRP) allocation engines. |
| **Paper Trading** | Live-market simulation that tracks hypothetical fills against real price feeds. |
| **Streamlit UI** | Launch a local dashboard with `qr.run_terminal()` — no frontend code required. |

## Who Is It For?

- **Individual quants** who want a batteries-included research stack
- **PMs at small funds** who need signal research + validation + paper trading in one repo
- **Students & researchers** learning systematic trading with production-grade tools
- **OpenBB users** looking to add backtesting, sentiment, and portfolio optimization on top of OpenBB's data layer

## Quick Links

- [Quickstart Guide](quickstart.md) — Install and run your first backtest in 5 minutes
- [Architecture Overview](architecture.md) — How the modules fit together
- [OpenBB Comparison](openbb_comparison.md) — How Alpha Search complements OpenBB
- [Roadmap](roadmap.md) — What's shipping and when
- [Agent Swarm](agent_swarm.md) — The 8-agent development structure

## Installation

```bash
pip install alpha-search
```

For development:

```bash
git clone https://github.com/alpha-search/alpha-search.git
cd alpha-search
pip install -e ".[dev]"
```

## One-Minute Example

```python
from alpha_search import Terminal

qr = Terminal(universe=["AAPL", "BTC-USD"])
prices = qr.data.get_prices("AAPL", start="2023-01-01", end="2024-01-01")
signal = qr.signals.momentum(prices, window=20)
results = qr.backtest.run(prices=prices, signal=signal, initial_capital=100000)
print(results.metrics)
```

## License

Alpha Search is released under the [MIT License](../LICENSE).
