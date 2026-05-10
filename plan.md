# Indian ETF Intraday Momentum Breakout — Implementation Plan

## Architecture
- **New module:** `alpha_search/signals/noise_breakout.py` — Noise area engine
- **New module:** `alpha_search/research/indian_etf_intraday.py` — Pipeline
- **New script:** `scripts/run_indian_etf_breakout.py` — CLI entry point
- **Reports:** `reports/indian_etf/` — All outputs

## Stage 1: Data + Noise Engine (Parallel)
- Fetch real Indian ETF data from yfinance (NIFTYBEES.NS, BANKBEES.NS, ITBEES.NS, JUNIORBEES.NS)
- Implement NoiseArea class with rolling volatility bands
- Test 20/45/90 day lookbacks

## Stage 2: Signals + Backtest (Parallel)
- Long: price breaks above upper noise band
- Short: price breaks below lower noise band
- Exit: re-enter noise area, end of session, trailing stop
- Backtest with 10bps costs + slippage

## Stage 3: Portfolio + Risk
- Equal weight, inverse volatility, risk parity
- Volatility targeting (1%, 2%, 3%)
- Max 3x leverage cap
- Max daily loss limit

## Stage 4: Memory + Reports
- Store parameter combos, Sharpe, drawdowns to DuckDB
- Generate .md report, .csv metrics, trade log
- Create visualizations (equity curve, drawdown, Sharpe by ETF)

## Stage 5: Integration + Commit
- Wire into Alpha Search architecture
- Commit: `feat: add Indian ETF intraday breakout research pipeline`
