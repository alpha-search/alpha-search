# Architecture Overview

Alpha Search is built around a small set of composable modules that share pandas objects as their lingua franca. Every module is independently testable and can be used without the others.

---

## System Diagram

```
                    External APIs
              +----------+-----------+
              |          |           |
         Yahoo Fin.   Binance    News RSS
              |          |           |
              +----------+-----------+
                         |
              +----------v-----------+
              |   Provider Registry  |
              |  (yahoo | binance)  |
              +----------+-----------+
                         |
              +----------v-----------+
              |   Cache Manager      |
              |   (DuckDB)           |
              +----------+-----------+
                         |
          +--------------+--------------+
          |              |              |
 +--------v------+ +-----v------+ +----v--------+
 |  Data Module  | |  Sentiment | |  Signals    |
 |  (OHLCV)      | |  (FinBERT) | |  (vector)   |
 +--------+------+ +-----+------+ +----+--------+
          |              |              |
          +--------------+--------------+
                         |
              +----------v-----------+
              |   Backtest Engine    |
              |   (vectorised)       |
              +----------+-----------+
                         |
         +---------------+---------------+
         |               |               |
 +-------v------+ +------v------+ +-----v-------+
 | Walk-Forward | |  Portfolio  | |   Metrics   |
 | Validation   | | Optimization| |   (Sharpe)  |
 +--------------+ +-------------+ +-------------+
         |               |               |
         +---------------+---------------+
                         |
              +----------v-----------+
              |   Streamlit UI       |
              |   / REST API         |
              +----------------------+
```

---

## Module Descriptions

### 1. Provider Registry (`alpha_search.data_providers`)

A plugin-style registry that maps source names (`"yahoo"`, `"binance"`) to provider classes. Each provider implements:

- `get_prices(ticker, start, end) -> pd.DataFrame`
- `get_fundamentals(ticker) -> pd.DataFrame`

Adding a new source means writing one class and calling `registry.register("name", MyProvider)`.

### 2. Cache Manager (`alpha_search.cache`)

DuckDB-backed key-value store with TTL. Serialises arbitrary Python objects via `pickle`. Used automatically by the data layer so repeated fetches hit local disk instead of the network.

Key design decisions:
- **DuckDB over SQLite**: faster analytical queries, native Parquet support
- **Pickle over JSON**: preserves pandas indexes, numpy arrays, and nested structures
- **TTL by default**: stale data is evicted automatically; cache hits are O(1)

### 3. Data Module (`alpha_search.data`)

The user-facing facade. Given a ticker and date range it:
1. Checks the cache
2. Delegates to the registered provider on miss
3. Normalises column names (`Open` -> `open`)
4. Writes back to cache
5. Returns a `pd.DataFrame`

### 4. Signals Module (`alpha_search.signals`)

Vectorised signal primitives operating on `pd.Series`:

| Function | Description |
|---|---|
| `momentum(prices, window)` | Rate of change over *window* bars |
| `ma_crossover(prices, short, long)` | +1 when short MA > long MA, -1 otherwise |
| `z_score_mean_reversion(prices, window, threshold)` | Short when z-score > threshold, long when < -threshold |
| `ensemble(signals, weights)` | Weighted average of aligned signal Series |
| `compose_and(a, b)` | Element-wise logical AND (+1 only when both are +1) |
| `compose_or(a, b)` | Element-wise logical OR (+1 when either is +1) |

All functions are pure: they take a Series and parameters, return a Series. No side effects, no global state.

### 5. Backtest Engine (`alpha_search.backtest`)

Vectorised event-based backtester. Input: a price Series and a signal Series. Output: an `BacktestResult` dataclass containing:

- `equity_curve` — portfolio value over time
- `positions` — fraction of capital invested per bar
- `trades` — entry/exit log
- `metrics` — Sharpe, return, drawdown, win-rate, etc.

Transaction costs are applied as a fractional spread per trade. Slippage can be modelled as a random perturbation.

### 6. Walk-Forward Module (`alpha_search.walk_forward`)

Rolling-window cross-validation for time series. Produces train/test index pairs that respect chronological ordering. Computes in-sample / out-of-sample degradation ratios to flag overfitting.

### 7. Sentiment Module (`alpha_search.sentiment`)

Wraps a FinBERT transformers pipeline for financial text. Provides:

- `analyze(text) -> {"label": str, "confidence": float}`
- `analyze_batch(texts) -> list[dict]`
- `composite_score(results, weights) -> float` (-1 to +1)

Optional dependency: install with `pip install "alpha-search[sentiment]"`.

### 8. Portfolio Optimization (`alpha_search.portfolio`)

Allocation engines:

- **Mean-Variance** — classical Markowitz with shrinkage covariance
- **Risk Parity** — equal risk contribution across assets
- **HRP** — hierarchical risk parity via inverse-variance clustering

### 9. Terminal (`alpha_search.terminal`)

The orchestrator. Holds references to every module and exposes:

- `qr.data.*` — data fetching
- `qr.signals.*` — signal generation
- `qr.backtest.*` — backtesting
- `qr.sentiment.*` — sentiment (if installed)
- `qr.portfolio.*` — optimisation (if installed)
- `qr.run_terminal()` — launch Streamlit UI

---

## Data Flow

A single research workflow looks like this:

```
External API (Yahoo Finance)
       |
       v
Provider.get_prices()  ----miss---->  Cache.set()
       |                                  |
       |<------------------------------hit|
       v
DataFrame (OHLCV)
       |
       +---> signals.momentum()  --->  signal Series
       |                                  |
       +---> sentiment.analyze() --->  sentiment score
                                          |
                                          v
                                   backtest.run()
                                          |
                     +--------------------+--------------------+
                     |                    |                    |
                     v                    v                    v
               equity_curve         metrics dict      walk_forward.validate()
                     |                    |                    |
                     +--------------------+--------------------+
                                          |
                                          v
                                   Streamlit UI / CLI
```

Every arrow is a pure function call on pandas objects. There are no hidden database writes, no global caches, no mutable shared state.

---

## Design Principles

### Vectorised Everything

Loops are forbidden in hot paths. Signal generation, backtesting, and metrics all use NumPy/pandas vector operations. A 10-year daily backtest completes in milliseconds.

### Modular and Composable

Each module can be imported and used standalone:

```python
from alpha_search.signals import momentum
from alpha_search.backtest import BacktestEngine
```

There is no god object. The `Terminal` is a convenience wrapper, not a requirement.

### Local-First

Data is cached locally in DuckDB. No cloud account required. No API keys for Yahoo Finance. Works on an airplane.

### Type-Safe

Every public function has type annotations. mypy is enforced in CI with `disallow_untyped_defs = true`.

### Tested

80 % coverage minimum. All external APIs are mocked in unit tests. Integration tests run nightly against live endpoints.
