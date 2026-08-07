# SOXX Intraday Research Pipeline

An end-to-end, **honest** intraday research pipeline for **SOXX** (iShares
Semiconductor ETF), with SMH and NVDA as correlated references. Built to be
skeptical: it is designed to tell you when a result is noise — and on a 60-day
sample with dozens of strategies, it usually is.

## ⚠️ Data note
This repository was developed in a sandbox whose network policy **blocks all
market-data hosts** (Yahoo, Stooq, AlphaVantage, Polygon, IEX, Nasdaq — all 403).
The data layer therefore falls back to a **clearly-labeled synthetic generator**
(`data/_provenance.json` records `SYNTHETIC` vs `yfinance`). Synthetic output is
**not** evidence of any edge — it exists only to exercise the code. Run this on a
machine with Yahoo access (e.g. a phone terminal) and the same code pulls **real**
5-minute bars automatically.

## Layout
```
soxx_research/
├── data/           cached parquet/csv bars + _provenance.json
├── src/
│   ├── data.py            Stage 1 — pull/clean/cache (yfinance + synthetic fallback)
│   ├── signals.py         Stage 2 — 7 signal families, each -> {-1,0,+1}
│   ├── backtest.py        Stage 3 — vectorized next-bar backtester + stats
│   ├── test_backtest.py   no-lookahead / correctness tests
│   ├── run_stage3.py      Stage 3 driver — leaderboard + deflated Sharpe + permutation
│   ├── paper_backtest.py  Stage 4 — event-driven $100k paper sim + equity_curve.png
│   ├── paper_live.py       Stage 4 — live signal printer (run during market hours)
│   └── report.py          Stage 5 — results/REPORT.md + 10-line summary
├── results/        leaderboard.csv, stats.json, paper_trades.csv, equity_curve.png, REPORT.md
└── run_all.py      runs Stage 1 -> 5
```

## Quickstart
```bash
cd soxx_research
pip install pandas numpy yfinance pyarrow scipy matplotlib
python3 run_all.py          # everything, in order
# or stage by stage:
python3 src/data.py
python3 src/signals.py
python3 src/test_backtest.py
python3 src/run_stage3.py
python3 src/paper_backtest.py
python3 src/report.py
python3 src/paper_live.py    # during market hours, on a machine with Yahoo access
```

## Signal families (Stage 2)
1. **TS-momentum** — N-bar return breakout (N = 3, 6, 12, 24).
2. **Opening-range breakout** — 15 / 30 / 60-minute OR.
3. **Mean reversion** — z-score vs rolling VWAP, Bollinger fade, RSI(2) extremes.
4. **Vol-regime breakout** — ATR-normalized breakout gated to a vol tercile.
5. **Time-of-day** — first hour / lunch / last hour, each direction, tested separately.
6. **Cross-asset lead-lag** — does NVDA / SMH last-bar return predict next-bar SOXX?
7. **Gap behavior** — overnight gap continuation vs fade.

Every signal has an explicit entry / exit / stop rule (see docstrings) and outputs
a causal target position in `{-1, 0, +1}`.

## Honesty machinery (Stage 3)
- **Next-bar execution**, asserted look-ahead-free in `test_backtest.py`.
- **Costs:** 1 bp commission + 2 bp slippage per side, plus a zero-cost view.
- **Deflated Sharpe Ratio** for the winner (multiple-testing correction).
- **70/30 train/hold-out** split — both Sharpes reported side by side.
- **500× permutation test** for the winner's Sharpe vs the null.

See `results/REPORT.md` for the verdict.
