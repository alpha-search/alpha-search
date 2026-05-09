# Alpha Search — Real Data Strategy Research Report

**Run Date:** 20260509_054019
**Universe:** `us_large_cap`
**Period:** 2019-01-01 → 2026-05-09
**Capital:** $100,000.00  **Tx Cost:** 0.10%

---

## ⚠️  FALLBACK DATA WARNING

> **All price data in this run is SYNTHETIC.** Yahoo Finance rate-limited the data requests. The pipeline executed successfully using realistic synthetic data to validate all components. **These results are NOT real backtest performance.**

---

## Liquidity Summary

| Ticker | Avg Daily Vol | Avg $ Vol | Missing % | Rank |
|--------|--------------|-----------|-----------|------|
| UNH | 27,082,227 | $39,946,660,979 | 0.00% | 1 |
| JPM | 27,599,731 | $12,411,380,532 | 0.00% | 2 |
| SPY | 27,766,210 | $12,325,624,091 | 0.00% | 3 |
| META | 27,648,526 | $11,832,445,515 | 0.00% | 4 |
| AAPL | 27,747,978 | $11,623,561,380 | 0.00% | 5 |
| TSLA | 27,369,870 | $10,622,052,871 | 0.00% | 6 |
| NVDA | 27,093,688 | $8,569,820,083 | 0.00% | 7 |
| MSFT | 27,097,788 | $8,544,426,483 | 0.00% | 8 |
| QQQ | 27,676,249 | $7,882,991,866 | 0.00% | 9 |
| GOOGL | 26,998,923 | $6,713,577,824 | 0.00% | 10 |

## Strategy Results

| Strategy | Total Ret | Ann Ret | Ann Vol | Sharpe | Max DD | Win Rate |
|----------|-----------|---------|---------|--------|--------|----------|
| momentum | 25.2728 | 0.5361 | 0.2816 | 1.9035 | -0.2874 | 0.5248 |
| mean_reversion | -1.0000 | -0.9405 | 0.1753 | -5.3643 | -1.0000 | 0.0740 |
| arbitrage_JPM_MSFT | -0.2761 | -0.0415 | 0.1185 | -0.3506 | -0.4060 | 0.0719 |
| arbitrage_NVDA_UNH | 0.0481 | 0.0062 | 0.0800 | 0.0773 | -0.1570 | 0.0526 |
| arbitrage_TSLA_XOM | 0.1804 | 0.0220 | 0.4209 | 0.0523 | -0.6908 | 0.0703 |
| arbitrage_AMZN_MSFT | -0.2402 | -0.0354 | 0.1015 | -0.3492 | -0.3258 | 0.0823 |
| arbitrage_AAPL_TSLA | -0.4909 | -0.0848 | 0.1104 | -0.7686 | -0.5160 | 0.0808 |
| portfolio_equal_weight | 1.4187 | 0.1230 | 0.0726 | 1.6945 | -0.0796 | 0.5407 |
| portfolio_inverse_volatility | 1.3465 | 0.1186 | 0.0729 | 1.6261 | -0.0829 | 0.5355 |
| portfolio_risk_parity | 1.2811 | 0.1144 | 0.0743 | 1.5393 | -0.0864 | 0.5334 |

## Generated Files

- `arbitrage_pairs_results.csv`
- `liquidity_summary.csv`
- `mean_reversion_results.csv`
- `memory_records_created.csv`
- `metadata.json`
- `momentum_results.csv`
- `portfolio_optimization_results.csv`
- `price_data.csv`
- `real_data_strategy_report.md`
- `returns_data.csv`
- `strategy_results_summary.csv`

## Disclaimer

> This research is for informational and educational purposes only. It does not constitute investment advice. Past performance is not indicative of future results. Always consult a qualified financial advisor before making investment decisions.
