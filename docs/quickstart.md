# Quickstart Guide

Get from zero to a running backtest in under 5 minutes.

---

## Step 1 — Install Alpha Search

```bash
# From PyPI (recommended)
pip install alpha-search

# With optional extras
pip install "alpha-search[sentiment]"   # FinBERT sentiment analysis
pip install "alpha-search[api]"         # FastAPI REST server
pip install "alpha-search[dev]"         # Test & lint tooling
```

Verify the install:

```bash
python -c "from alpha_search import Terminal; print('Alpha Search', Terminal.__module__)"
```

---

## Step 2 — Fetch Market Data

```python
from alpha_search import Terminal

# Initialise the terminal with your universe
qr = Terminal(universe=["AAPL", "MSFT", "GOOGL", "BTC-USD"])

# Pull daily OHLCV for a single ticker
prices = qr.data.get_prices(
    "AAPL",
    start="2023-01-01",
    end="2024-01-01",
)
print(prices.head())
```

Output:

```
                open     high      low    close    volume
2023-01-03  130.280  130.900  124.170  125.070  112117500
2023-01-04  126.890  128.655  125.080  126.360   89113600
...
```

The data layer automatically:
- Fetches from Yahoo Finance (or your configured provider)
- Caches results in a local DuckDB file
- Normalises columns to lowercase `open/high/low/close/volume`
- Returns a pandas DataFrame with a DatetimeIndex

---

## Step 3 — Generate a Signal

```python
# Simple 20-day momentum signal
signal = qr.signals.momentum(prices.close, window=20)

# Or a moving-average crossover
cross = qr.signals.ma_crossover(prices.close, short=10, long=30)

# Combine them with an ensemble
ensemble = qr.signals.ensemble(
    {"mom": signal, "cross": cross},
    weights={"mom": 0.6, "cross": 0.4},
)
```

Signals are pandas Series with the same index as `prices` and values in `[-1, 1]`:
- `+1`  → full long
- `0`   → flat / no position
- `-1`  → full short

---

## Step 4 — Run a Backtest

```python
results = qr.backtest.run(
    prices=prices.close,
    signal=ensemble,
    initial_capital=100_000,
    transaction_cost=0.001,  # 10 bps per trade
)

print(results.metrics)
```

Output:

```python
{
    "total_return": 0.247,
    "sharpe_ratio": 1.42,
    "max_drawdown": 0.083,
    "num_trades": 34,
    "win_rate": 0.56,
}
```

Access the full equity curve:

```python
import matplotlib.pyplot as plt

results.equity_curve.plot(figsize=(10, 4), title="Strategy Equity Curve")
plt.show()
```

---

## Step 5 — Launch the Streamlit UI

```python
qr.run_terminal()
```

Or from the command line:

```bash
alpha-search
```

This starts a local web server (default `http://localhost:8501`) with:
- Interactive ticker selection
- Real-time signal visualisation
- Backtest parameter tuning
- Equity-curve and drawdown charts (Plotly)
- Metrics summary cards

---

## Next Steps

- Read the [Architecture Overview](architecture.md) to understand how modules connect
- Explore [Walk-Forward Validation](architecture.md#walk-forward-module) to avoid overfitting
- Add [Sentiment Signals](architecture.md#sentiment-module) via FinBERT
- Compare with [OpenBB](openbb_comparison.md) if you're migrating

## Troubleshooting

**ImportError: No module named 'alpha_search'**
> Ensure you installed with `pip install -e ".[dev]"` inside the repo root, or `pip install alpha-search` for the PyPI release.

**yfinance rate-limited**
> The DuckDB cache will serve previously fetched data. Increase TTL with `qr.data.cache.set(..., ttl_seconds=86400)`.

**Streamlit port already in use**
> Launch on a different port: `qr.run_terminal(port=8502)`.
