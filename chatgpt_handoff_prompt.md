# Alpha Search v0.2.2 — Real Data Backtesting Pipeline (Handoff Prompt)

**Context:** I just finished a session with Claude Code that extended the `alpha_search` Python codebase. Here's what was built and where things stand.

**Branch:** `claude/comprehensive-code-review-d9880`
**Commit:** `178f78a`
**Test suite:** 161 tests pass (no regressions)

---

## What Was Built

### 1. `alpha_search/research/real_data_pipeline.py` — 12 new standalone functions

| Function | Description |
|---|---|
| `fetch_yfinance_ohlcv(symbols, period, interval)` | Fetches each symbol independently; skips failures; never fabricates data |
| `load_csv_ohlcv(filepath)` | Loads real OHLCV from CSV (`timestamp,symbol,open,high,low,close,volume`) |
| `validate_ohlcv(df, ticker)` | Validates required columns, min rows, non-positive close (hard fail), OHLCV integrity |
| `generate_momentum_signal(close, lookback, ma_confirm)` | MA-crossover confirmed momentum |
| `generate_mean_reversion_signal(close, window, z_threshold)` | z-score based mean reversion |
| `generate_breakout_signal(close, high, low, window)` | Donchian channel with `shift(1)` to prevent lookahead |
| `run_vectorized_backtest(close, signal, ...)` | Wraps `BacktestEngine` with bps cost params |
| `calculate_metrics(result)` | Extends core metrics with `num_trades`, `exposure`, `turnover` |
| `export_research_outputs(results, base_dir)` | Timestamped output dir with `metadata.json`, CSVs, `report.md`, figures |
| `run_real_data_research(universe, period, ...)` | Full orchestrator with honest Sharpe verdicts |

**Sharpe verdicts:** `promising` (> 1.0) · `marginal` (0–1.0) · `unprofitable` (≤ 0) · `no_results` (no trades)

**Universe constants:**

```python
UNIVERSE_US_LARGE_CAP  # AAPL, MSFT, NVDA, GOOGL, AMZN, META, JPM, XOM, UNH, SPY, QQQ
UNIVERSE_INDIA_EQUITY  # NIFTYBEES.NS, HDFCBANK.NS, RELIANCE.NS, INFY.NS, ...
UNIVERSE_CRYPTO        # BTC-USD, ETH-USD, SOL-USD
UNIVERSES              # dict with keys: us_large_cap, india_equity, crypto, all
```

---

### 2. `notebooks/01_real_data_backtesting_colab.ipynb` — 15-section Colab notebook

1. Install dependencies
2. Clone and install Alpha Search
3. Imports
4. Research disclaimer
5. Data source configuration
6. Real data ingestion
7. Data validation
8. Signal generation
9. Backtest engine
10. Transaction costs & slippage
11. Metrics calculation
12. Visualisation (equity curves, drawdown, rolling Sharpe)
13. CSV export
14. Markdown report export
15. Research conclusion

---

### 3. `scripts/run_real_data_backtest.py` — CLI script

```bash
python scripts/run_real_data_backtest.py \
  --universe us_large_cap \
  --period 2y \
  --interval 1d \
  --cost-bps 10 \
  --slippage-bps 10

# Flags
--universe       us_large_cap | india_equity | crypto | all
--period         yfinance period string (1y, 2y, 5y, max)
--interval       bar interval (1d, 1h, 30m)
--output-dir     base directory for timestamped results (default: outputs/research_runs)
--cost-bps       commission in basis points (default: 10)
--slippage-bps   slippage in basis points (default: 10)
--csv-file       path to local CSV file (skips yfinance download)
--json-summary   print machine-readable JSON summary to stdout
--log-level      DEBUG | INFO | WARNING | ERROR
```

---

### 4. `tests/test_real_data_pipeline.py` — 57 unit tests

All mocked — no live network calls. Covers:

- Universe constants
- `fetch_yfinance_ohlcv` (success, failure, partial, empty, title-case columns)
- `load_csv_ohlcv` (single symbol, multi-symbol, missing file, datetime index)
- `validate_ohlcv` (valid, empty, missing Close, too few rows, non-positive close, High < Close)
- `generate_momentum_signal` (returns Series, bounded values, trending prices)
- `generate_mean_reversion_signal` (long-only, allow_short, dip triggers long)
- `generate_breakout_signal` (no lookahead via shift, trending prices, high/low provided)
- `run_vectorized_backtest` (BacktestResult type, equity start, cost drag, flat signal = no trades)
- `calculate_metrics` (core keys, extended keys, exposure 0–1, flat signal zero exposure)
- `export_research_outputs` (creates dir, metadata.json, report.md, summary CSV)

---

### 5. Other files

| File | Purpose |
|---|---|
| `outputs/research_runs/.gitkeep` | Tracks output directory in git |
| `.gitignore` | Added `!notebooks/*.ipynb` exception to allow notebook tracking |

---

## Critical Constraints Respected

- **No synthetic data** — real OHLCV only
- **No FRED** as tradable price data
- **No fake Sharpe claims** — negative results reported honestly
- **Skip and log** on yfinance failure — data is never fabricated
- **`shift(1)` before `rolling()`** throughout all signal generators to prevent lookahead bias
- **Tests are fully mocked** — `yfinance.download` is patched; no internet required to run tests

---

## Codebase

- **Location:** `/home/user/alpha-search`
- **Package:** `alpha_search` (Python, install with `pip install -e .`)
- **Branch:** `claude/comprehensive-code-review-d9880`

---

What would you like to do next with this codebase?
